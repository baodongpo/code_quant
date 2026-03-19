/**
 * utils/auth.js — Token 读取 / 存储 / URL 清理
 *
 * 使用方式：
 *   在 main.jsx 顶部调用 initAuth()，从 URL ?token= 读取并存入 localStorage；
 *   API 请求拦截器调用 getToken() 获取 token 后附加到请求头。
 */

const TOKEN_KEY = 'access_token'

/**
 * 初始化鉴权：从 URL ?token= 读取 token，存入 localStorage，并清除 URL 中的 token 参数。
 * 在应用启动时调用一次即可。
 */
export function initAuth() {
    const params = new URLSearchParams(window.location.search)
    const urlToken = params.get('token')
    if (urlToken) {
        localStorage.setItem(TOKEN_KEY, urlToken)
        params.delete('token')
        const newUrl =
            window.location.pathname +
            (params.toString() ? '?' + params : '') +
            window.location.hash
        window.history.replaceState({}, '', newUrl)
    }
}

/**
 * 获取当前存储的 token。
 * @returns {string} token 字符串，未设置时返回空字符串
 */
export function getToken() {
    return localStorage.getItem(TOKEN_KEY) || ''
}
