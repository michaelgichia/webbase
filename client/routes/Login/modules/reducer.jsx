import axios from 'axios'

import { getSessionLoggedIn } from '../../../actions/AuthActions'

// ====================================
// Constants
// ====================================

export const LOGIN_LOADING = 'LOGIN_LOADING'
export const LOGIN_ERROR = 'LOGIN_ERROR'
export const LOGIN_RESET_STATE = 'LOGIN_RESET_STATE'

// ====================================
// Actions
// ====================================

const logger = require('loglevel').getLogger('Login')
logger.setLevel(__LOGLEVEL__)

export function doLogin (data) {
  return dispatch => {
    dispatch({type: LOGIN_LOADING})

    axios.post('/api/login', data)
      .then((response) => {
        logger.debug('/api/login (data) (response)', data, response)

        if (response.data.success) {
          dispatch(resetLoginState())
          dispatch(getSessionLoggedIn(response.data))
        } else {
          dispatch(loginError(response.data.error))
        }
      })
      .catch((response) => {
        logger.debug('/api/login error (data) (response)', data, response)
        dispatch(loginError(response.data.error))
      })
  }
}

function loginError (error) {
  return {
    type: LOGIN_ERROR,
    error
  }
}

export function resetLoginState () {
  return dispatch => {
    dispatch({type: LOGIN_RESET_STATE})
  }
}

export const actions = {
  doLogin,
  resetLoginState
}

// ====================================
// Reducers
// ====================================

const initialState = {
  loading: false,
  error: null
}

export default function login (state = initialState, action) {
  switch (action.type) {
    case LOGIN_LOADING:
      return Object.assign({},
        state,
        {
          loading: true,
          error: null
        }
      )

    case LOGIN_ERROR:
      return Object.assign({},
        state,
        {
          loading: false,
          error: action.error
        }
      )
    case LOGIN_RESET_STATE:
      return Object.assign({},
        state,
        {
          loading: false,
          error: null
        }
      )
    default:
      return state
  }
}
