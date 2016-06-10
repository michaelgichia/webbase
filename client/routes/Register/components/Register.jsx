import React from 'react'
import { Link } from 'react-router'
import { defineMessages, FormattedMessage } from 'react-intl'

import SecureFormStyle from 'components/ux/SecureFormStyle.postcss'
import SecureForm from 'components/ux/SecureForm'
import BaseComponent from 'core/BaseComponent'
import ErrorMsg from 'components/ux/ErrorMsg'
import ValidatedInput from 'components/ux/Input'
import LaddaButton from 'components/ux/LaddaButton'
import PasswordInput from 'components/ux/PasswordInput'

const registerMessages = defineMessages({
  emailPlaceholder: {
    id: 'register.EmailPlaceholder',
    defaultMessage: 'Email address'
  },
  namePlaceholder: {
    id: 'register.NamePlaceholder',
    defaultMessage: 'Name'
  },
  passwordPlaceholder: {
    id: 'register.PasswordPlaceholder',
    defaultMessage: 'Password'
  }
})

class Register extends BaseComponent {
  constructor (props) {
    super(props)

    this._initLogger()
    this._bind('enableButton', 'disableButton', 'onSubmit')
  }

  onSubmit () {
    this.debug('onSubmit')

    this.props.actions.doRegister(this.refs.form.getModel())
  }

  enableButton () {
    this.debug('enableButton')
    this.refs.button.setState({ isDisabled: false })
  }

  disableButton () {
    this.debug('disableButton')
    this.refs.button.setState({ isDisabled: true })
  }

  render () {
    this.debug('render')

    const { formatMessage } = this._reactInternalInstance._context.intl
    const errorMsg = this.props.register.error ? <ErrorMsg msgId={this.props.register.error} /> : null
    const emailPlaceholder = formatMessage(registerMessages.emailPlaceholder)
    const namePlaceholder = formatMessage(registerMessages.namePlaceholder)
    const passwordPlaceholder = formatMessage(registerMessages.passwordPlaceholder)

    return (
      <center>
        <SecureForm ref='form' onValid={this.enableButton} onInvalid={this.disableButton} session={this.props.session}>
          <h2 className={SecureFormStyle['form-signin-heading']}>

            <FormattedMessage
              id='register.Registration'
              defaultMessage='Registration'
            />
          </h2>
          <ValidatedInput type='email' name='email' placeholder={emailPlaceholder} validations='isEmail' required autoFocus />
          <ValidatedInput type='text' name='name' placeholder={namePlaceholder} required validations='minLength:2' maxLength='60' />
          <PasswordInput type='password' name='password' placeholder={passwordPlaceholder} required />
          <LaddaButton ref='button' isDisabled isLoading={this.props.register.loading} onSubmit={this.onSubmit}>
            <FormattedMessage
              id='register.RegisterBtn'
              defaultMessage='Register'
            />
          </LaddaButton>
          <center>{errorMsg}</center>
        </SecureForm>
        <p>
          <Link to='/login'>
            <FormattedMessage
              id='register.AlreadyHaveAnAccount'
              defaultMessage='Already have an account? Log in here'
            />
          </Link>
        </p>
      </center>
    )
  }
}

export default Register
