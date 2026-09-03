var api = require('./utils/api')

App({
  onLaunch() {
    wx.showShareMenu({
      withShareTicket: true,
      menus: ['shareAppMessage', 'shareTimeline']
    })

    // Phase 1: 自动登录
    this.autoLogin()
  },

  autoLogin() {
    var that = this
    // 已有有效 token 则跳过
    var token = api.getToken()
    if (token) {
      console.log('[Auth] 已有 token，跳过登录')
      return
    }

    // 微信登录获取 code
    wx.login({
      success: function (res) {
        if (res.code) {
          console.log('[Auth] wx.login 成功, code:', res.code.substring(0, 10) + '...')
          // 调用后端登录接口
          api.wechatLogin(res.code).then(function (data) {
            api.setToken(data.token)
            console.log('[Auth] 登录成功, user_id:', data.user_id)
            // 保存用户信息到 globalData
            that.globalData.userInfo = {
              userId: data.user_id,
              nickname: data.nickname,
              isNewUser: data.is_new_user
            }
          }).catch(function (err) {
            console.error('[Auth] 登录失败:', err)
            // 非致命错误，使用 mock 登录作为 fallback
            if (err.code === 503 || err.code === -1) {
              console.log('[Auth] 尝试 mock 登录作为 fallback')
              api.wechatLogin('mock_miniprogram_user').then(function (data) {
                api.setToken(data.token)
                that.globalData.userInfo = {
                  userId: data.user_id,
                  nickname: data.nickname,
                  isNewUser: data.is_new_user
                }
              }).catch(function () {
                console.error('[Auth] mock 登录也失败了')
              })
            }
          })
        } else {
          console.error('[Auth] wx.login 失败:', res.errMsg)
        }
      },
      fail: function (err) {
        console.error('[Auth] wx.login 调用失败:', err)
      }
    })
  },

  globalData: {
    userInfo: null
  }
})
