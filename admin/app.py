import os
import importlib
import base64
import json
import logging
from logging.handlers import TimedRotatingFileHandler
import asyncio

from flask import flash
from flask_admin.babel import gettext, ngettext, lazy_gettext
from IPython import embed
from cryptography import fernet
from flask import Flask, url_for, redirect, render_template, request
from wtforms import form, fields, validators
import flask_admin as admin
import flask_login as login
from flask_admin import helpers, expose
from flask_admin.form import Select2Widget
from flask_admin.contrib.pymongo import ModelView, filters
import pymongo
from bson.objectid import ObjectId

from webbaseserver.utils import DbSessionContext
from webbaseserver.settings import config
from webbaseserver.exceptions import *  # noqa

loop = asyncio.get_event_loop()
asyncio.set_event_loop(loop)


HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.join(HERE, '..')

# CONFIG

config_path = os.path.join(ROOT, 'configs', 'server.json')
config.configure(config_path)

# LOGGING

## DISABLE werkzeug
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(logging.ERROR)

## WEBBASE ADMIN
logger = logging.getLogger('webbase_admin')
logger.setLevel(getattr(logging, config.get('ADMIN').get('LOG_LEVEL', 'INFO')))

formatter = logging.Formatter(
    '[L:%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s',
    datefmt='%d-%m-%Y %H:%M:%S'
)

## StreamHandler
sh = logging.StreamHandler()
sh.setFormatter(formatter)
logger.addHandler(sh)

## FileHandler
fh = TimedRotatingFileHandler(
    os.path.join(ROOT, 'logs', 'admin_server.log'),
    when="midnight"
)
fh.setFormatter(formatter)
logger.addHandler(fh)

conn = pymongo.Connection()
db = getattr(conn, config.get('MONGO_DATABASE_NAME'))

app = Flask(__name__)

fernet_key = fernet.Fernet.generate_key()
secret_key = base64.urlsafe_b64decode(fernet_key)
app.config['SECRET_KEY'] = secret_key

class BaseView(ModelView):
    def get_list(self, *args, **kwargs):
        count, data = super(BaseView, self).get_list(*args, **kwargs)

        query = {'_id': {'$in': [x['user_uid'] for x in data]}}
        users = db.User.find(query, fields=('email',))

        users_map = dict((x['_id'], x['email']) for x in users)

        for item in data:
            item['user_email'] = users_map.get(item['user_uid'])

        return count, data

    def _feed_user_choices(self, form):
        users = db.User.find(fields=('email',))
        form.user_uid.choices = [(str(x['_id']), x['email']) for x in users]
        return form

    def create_form(self):
        form = super(BaseView, self).create_form()
        return self._feed_user_choices(form)

    def edit_form(self, obj):
        form = super(BaseView, self).edit_form(obj)
        return self._feed_user_choices(form)

    def on_model_change(self, form, model):
        user_uid = model.get('user_uid')
        model['user_uid'] = ObjectId(user_uid)

        return model



class EmailConfirmationTokenForm(form.Form):
    user_uid = fields.SelectField('User', widget=Select2Widget())
    token = fields.TextField()
    used = fields.BooleanField()


class EmailConfirmationTokenView(BaseView):
    column_list = ('token', 'user_email', 'used')
    column_sortable_list = ('token', 'user_email', 'used')

    form = EmailConfirmationTokenForm

    def is_accessible(self):
        return login.current_user.is_authenticated()


class ForgottenPasswordtokenForm(form.Form):
    user_uid = fields.SelectField('User', widget=Select2Widget())
    token = fields.TextField()
    used = fields.BooleanField()


class ForgottenPasswordtokenView(BaseView):
    column_list = ('token', 'user_email', 'used')
    column_sortable_list = ('token', 'user_email', 'used')

    form = ForgottenPasswordtokenForm

    def is_accessible(self):
        return login.current_user.is_authenticated()


class NotificationForm(form.Form):
    user_uid = fields.SelectField('User', widget=Select2Widget())
    message = fields.TextField()
    template_data = fields.TextAreaField()  # TODO add validation
    seen = fields.BooleanField()
    target_url = fields.TextField()


class NotificationView(BaseView):
    column_list = ('user_uid', 'user_email', 'message')
    column_sortable_list = ('user_uid', 'user_email', 'message', 'seen_timestamp')

    form = NotificationForm

    def is_accessible(self):
        return login.current_user.is_authenticated()

class UserForm(form.Form):
    name = fields.TextField('Name', [validators.DataRequired()])
    email = fields.TextField('Email', [validators.DataRequired(), validators.Email()])
    role = fields.SelectField('Role', choices=[('admin', 'admin'), ('user', 'user')])
    enable = fields.BooleanField('Enable')
    email_confirmed = fields.BooleanField('Email confirmed')

class UserView(ModelView):
    column_list = ('name', 'email', 'role', 'enable', 'email_confirmed')
    column_sortable_list = ('name', 'email', 'role', 'enable', 'email_confirmed')
    column_searchable_list = ('name', 'email')

    form = UserForm

    def is_accessible(self):
        return login.current_user.is_authenticated()

    def on_model_change(self, form, model):
        with DbSessionContext(config.get('MONGO_DATABASE_NAME')) as session:
            try:
                m = importlib.import_module(
                    'webbaseserver.model.{model}'.format(model=self.name.lower())
                )
                model_class = getattr(m, self.name.title())

                model_obj = session.query(model_class)\
                    .filter(model_class.mongo_id == model['_id'])\
                    .one()

                context = {}
                context['db_session'] = session
                context['author'] = login.current_user
                context['data'] = form.data

                loop.run_until_complete(model_obj.validate_and_save(context))

            except Exception as e:
                if isinstance(e, ServerBaseException):
                    flash(gettext('Failed to update record. %(exception)s(%(error)s)', exception=e.get_name(), error=e),
                          'error')
                else:
                    flash(gettext('Failed to update record. %(error)s', error=e),
                          'error')
                return False

            return True

class Admin(object):

    username = config.get('ADMIN').get('USERNAME')
    password = config.get('ADMIN').get('PASSWORD')
    role= 'admin'

    def __repr__(self):
        return "Admin"

    def is_authenticated(self):
        # logger.debug('Admin.is_authenticated')
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return self.username

    def __unicode__(self):
        return self.username


class LoginForm(form.Form):
    login = fields.TextField(validators=[validators.required()])
    password = fields.PasswordField(validators=[validators.required()])

    def validate_login(self, field):
        user = self.get_user()

        if user is None:
            raise validators.ValidationError('Invalid user')

        if user.password != self.password.data:
            raise validators.ValidationError('Invalid password')

    def get_user(self):
        if self.login.data == config.get('ADMIN').get('USERNAME'):
            return Admin()
        else:
            return None


def init_login():
    login_manager = login.LoginManager()
    login_manager.init_app(app)
    if config.get('ADMIN').get('ENV', 'production') == 'development':
        login.current_user = Admin()

    @login_manager.user_loader
    def load_user(user_id):
        embed()
        if user_id == config.get('ADMIN').get('USERNAME'):
            return Admin()
        else:
            return None


class MyAdminIndexView(admin.AdminIndexView):

    @expose('/')
    def index(self):
        if not login.current_user.is_authenticated():
            # logger.debug('not login.current_user.is_authenticated() redirect to login_view')
            return redirect(url_for('.login_view'))
        return super(MyAdminIndexView, self).index()

    @expose('/login/', methods=('GET', 'POST'))
    def login_view(self):
        form = LoginForm(request.form)
        if helpers.validate_form_on_submit(form):
            user = form.get_user()
            login.login_user(user)

        if login.current_user.is_authenticated():
            # logger.debug('login.current_user.is_authenticated() redirect to index')
            return redirect(url_for('.index'))
        self._template_args['form'] = form
        return super(MyAdminIndexView, self).index()

    @expose('/logout/')
    def logout_view(self):
        login.logout_user()
        return redirect(url_for('.index'))


@app.route('/')
def index():
    return redirect(url_for('admin.index'))


init_login()

admin = admin.Admin(app, 'Webbase - admin', index_view=MyAdminIndexView(), base_template='my_master.html')
admin.add_view(UserView(db.User, 'User'))
admin.add_view(NotificationView(db.Notification, 'Notification'))
admin.add_view(EmailConfirmationTokenView(db.EmailConfirmationToken, 'EmailConfirmationToken'))
admin.add_view(ForgottenPasswordtokenView(db.ForgottenPasswordtoken, 'ForgottenPasswordtoken'))

if __name__ == '__main__':
    host = config.get('ADMIN').get('HOST')
    port = config.get('ADMIN').get('PORT')
    app.run(host=host, port=31337, debug=False)
