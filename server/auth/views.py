import importlib

from aiohttp_session import get_session
from aiohttp import web

from server.exceptions import *  # noqa
from server.model.user import User
from server.model.email_confirmation_token import EmailConfirmationToken
from server.model.reset_password_token import ResetPasswordToken
from server.settings import logger
from server.server_decorator import require, exception_handler, csrf_protected
from server.prometheus_instruments import active_user_gauge


def get_user_from_session(session, db_session):
    try:
        return db_session.query(User)\
            .filter(User.mongo_id == session['uid']).one()
    except:
        return None


async def set_session(user, request):
    session = await get_session(request)
    session['uid'] = user.get_uid()
    active_user_gauge.inc()


class CRUDBase(web.View):
    async def get_json_data(self):
        try:
            resq_data = await self.request.json()
            datum = resq_data['data']
            model = resq_data['model']

            # Convert datum to list if necessary
            if not type(datum) == list:
                datum = [datum]
            logger.debug('datum = {datum}'.format(
                datum=datum
            ))

            return datum, model
        except:
            raise InvalidRequestException(
                'No json send or missing data parameters'
            )

    def import_model(self, model):
        try:
            m = importlib.import_module(
                'server.model.{model}'.format(model=model)
            )
            return getattr(m, model.title())
        except ImportError:
            raise ModelImportException('{model} not found'.format(model=model))


class CRUDCreate(CRUDBase):

    @exception_handler()
    @csrf_protected()
    @require('login')
    async def post(self):
        datum, model = await self.get_json_data()
        model_class = self.import_model(model)

        session = await get_session(self.request)
        user = get_user_from_session(session, self.request.db_session)

        context = {
            'user': user,
            'db_session': self.request.db_session,
            'method': 'create',
            'queue': self.request.app.queue
        }

        resp_datum = []
        for data in datum:
            model_obj = model_class()

            context['data'] = data
            context['method'] = 'create'

            if not await model_obj.method_autorized(context):
                raise NotAuthorizedException(
                    '{user} not authorized to create {model_class}'
                    .format(
                        user=user,
                        model_class=model_class
                    )
                )

            sane_data = await model_obj.sanitize_data(
                context
            )
            context['data'] = sane_data
            await model_obj.validate_and_save(context)

            context['method'] = 'read'
            resp_datum.append(await model_obj.serialize(context))

        resp_data = {'success': True, 'results': resp_datum}
        return web.json_response(resp_data)


class CRUDRead(CRUDBase):

    @exception_handler()
    @csrf_protected()
    @require('login')
    async def post(self):
        datum, model = await self.get_json_data()
        model_class = self.import_model(model)

        session = await get_session(self.request)
        user = get_user_from_session(session, self.request.db_session)

        context = {
            'user': user,
            'db_session': self.request.db_session,
            'method': 'read',
            'queue': self.request.app.queue
        }

        resp_datum = []
        for data in datum:
            uid = data.get('uid')

            # READ SPECIFIC RECORD
            if uid:
                results = self.request.db_session.query(model_class)\
                    .filter(model_class.mongo_id == uid).all()

            else:
                filters = data.get('filters')
                limit = data.get('limit')
                skip = data.get('skip')

                base_query = self.request.db_session.query(model_class)

                if limit:
                    base_query = base_query.limit(limit)

                if skip:
                    base_query = base_query.skip(skip)

                if filters:
                    if 'uid' in filters:
                        filters['mongo_id'] = filters['uid']
                        del filters['uid']

                    base_query = base_query.filter_by(**filters)

                results = base_query.all()

            for result in results:
                if not await result.method_autorized(context):
                    raise NotAuthorizedException(
                        '{user} not authorized to read {model_obj}'
                        .format(
                            user=user,
                            model_obj=result
                        )
                    )

                resp_datum.append(await result.serialize(context))

        resp_data = {'success': True, 'results': resp_datum}
        return web.json_response(resp_data)


class CRUDUpdate(CRUDBase):

    @exception_handler()
    @csrf_protected()
    @require('login')
    async def post(self):
        datum, model = await self.get_json_data()
        model_class = self.import_model(model)

        session = await get_session(self.request)
        user = get_user_from_session(session, self.request.db_session)

        context = {
            'user': user,
            'db_session': self.request.db_session,
            'method': 'update',
            'queue': self.request.app.queue
        }

        resp_datum = []
        for data in datum:
            uid = data.get('uid')
            if not uid:
                raise InvalidRequestException('Missing uid in request json')

            model_obj = self.request.db_session.query(model_class)\
                .filter(model_class.mongo_id == uid).one()

            context['method'] = 'update'
            if not await model_obj.method_autorized(context):
                raise NotAuthorizedException(
                    '{user} not authorized to update {model_obj}'
                    .format(
                        user=user,
                        model_obj=model_obj
                    )
                )

            context['data'] = data
            sane_data = await model_obj.sanitize_data(context)
            context['data'] = sane_data
            await model_obj.validate_and_save(context)
            context['method'] = 'read'
            resp_datum.append(await model_obj.serialize(context))

        resp_data = {'success': True, 'updated': resp_datum}
        return web.json_response(resp_data)


class CRUDDelete(CRUDBase):

    @exception_handler()
    @csrf_protected()
    @require('login')
    async def post(self):
        datum, model = await self.get_json_data()
        model_class = self.import_model(model)

        session = await get_session(self.request)
        user = get_user_from_session(session, self.request.db_session)

        context = {
            'user': user,
            'db_session': self.request.db_session,
            'method': 'delete',
            'queue': self.request.app.queue
        }

        resp_datum = []
        for data in datum:
            uid = data.get('uid')
            if not uid:
                raise InvalidRequestException('Missing uid in request json')

            model_obj = self.request.db_session.query(model_class)\
                .filter(model_class.mongo_id == uid).one()

            if not await model_obj.method_autorized(context):
                raise NotAuthorizedException(
                    '{user} not authorized to delete {model_obj}'
                    .format(
                        user=user,
                        model_obj=model_obj
                    )
                )

            self.request.db_session.remove(model_obj, safe=True)
            resp_datum.append({'uid': uid})

        resp_data = {'success': True, 'deleted': resp_datum}
        return web.json_response(resp_data)


class Login(web.View):

    @exception_handler()
    @csrf_protected()
    async def post(self):
        try:
            data = await self.request.json()
            email = data['email']
            password = data['password']
        except:
            raise InvalidRequestException('No json send')

        query = self.request.db_session.query(User)\
            .filter(User.email == email)
        if query.count():
            user = query.one()
            is_password_valid = await user.check_password(password)
            is_enable = user.enable
            if is_password_valid and is_enable:
                await set_session(user, self.request)

                context = {
                    'db_session': self.request.db_session,
                    'method': 'read',
                    'queue': self.request.app.queue
                }

                resp_data = {
                    'success': True,
                    'user': await user.serialize(context)
                }
            else:
                raise WrongEmailOrPasswordException()
        else:
            raise WrongEmailOrPasswordException(
                "Wrong email: '{email}'".format(email=email)
            )

        return web.json_response(resp_data)


class Register(web.View):

    @exception_handler()
    @csrf_protected()
    async def post(self):
        try:
            data = await self.request.json()
        except:
            raise InvalidRequestException('No json send')

        context = {
            'db_session': self.request.db_session,
            'method': 'create',
            'queue': self.request.app.queue
        }

        # INIT USER
        user = User()
        context['data'] = data
        sane_data = await user.sanitize_data(context)
        context['data'] = sane_data
        await user.validate_and_save(context)

        # SET SESSION
        await set_session(user, self.request)

        context['method'] = 'read'
        context['user'] = user
        resp_data = {'success': True, 'user': await user.serialize(context)}
        return web.json_response(resp_data)


class Logout(web.View):

    @exception_handler()
    @require('login')
    @csrf_protected()
    async def post(self):
        session = await get_session(self.request)
        user = get_user_from_session(session, self.request.db_session)
        user.logout(session)
        resp_data = {'success': True}
        return web.json_response(resp_data)


@exception_handler()
@require('admin')
async def api_admin(request):
    logger.debug('admin')
    session = await get_session(request)
    user = get_user_from_session(session, request.db_session)

    context = {
        'user': user,
        'db_session': request.db_session,
        'method': 'read',
        'queue': request.app.queue
    }

    resp_data = {'success': True, 'user': await user.serialize(context)}
    return web.json_response(resp_data)


@exception_handler()
@require('login')
async def api_confirm_email(request):
    logger.debug('confirm_email')

    try:
        data = await request.json()
        email_confirmation_token = data['token']
    except:
        raise InvalidRequestException('Missing json data')

    session = await get_session(request)
    user = get_user_from_session(session, request.db_session)

    context = {
        'user': user,
        'db_session': request.db_session,
        'method': 'update',
        'queue': request.app.queue
    }

    token_query = request.db_session.query(EmailConfirmationToken)\
        .filter(EmailConfirmationToken.token == email_confirmation_token)
    if token_query.count():
        email_confirmation_token = token_query.one()

        context['target'] = email_confirmation_token
        ret = email_confirmation_token.use(context)
        if ret:
            context['data'] = {'email_confirmed': True}
            del context['target']
            await user.validate_and_save(context)

            context['method'] = 'read'
            resp_data = {
                'success': True,
                'user': await user.serialize(context)
            }
            return web.json_response(resp_data)

    # TOKEN NOT FOUND
    else:
        raise TokenInvalidException('token not found')


@exception_handler()
@csrf_protected()
@require('login')
async def api_reset_password(request):
    logger.debug('reset_password')

    try:
        data = await request.json()
        new_password = data['password']
        token = data['reset_password_token']
    except:
        raise InvalidRequestException('Missing json data')

    session = await get_session(request)
    user = get_user_from_session(session, request.db_session)

    context = {
        'user': user,
        'db_session': request.db_session,
        'method': 'update',
        'queue': request.app.queue,
        'data': {'password': new_password}
    }

    token_query = request.db_session.query(ResetPasswordToken)\
        .filter(ResetPasswordToken.token == token)\
        .filter(ResetPasswordToken.user_uid == user.get_uid())
    if token_query.count():
        reset_password_token = token_query.one()
        if reset_password_token.token == token:
            await user.validate_and_save(context)

            resp_data = {'success': True}
            return web.json_response(resp_data)

        else:
            raise TokenInvalidException('Token mismatch')

    else:
        raise TokenInvalidException('Token not found')
