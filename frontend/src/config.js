/**
 * 墨林百科 — 全局站点配置
 * 所有品牌信息集中于此，改一处即可全局生效。
 * 未来可从后端 /api/v1/site-info 动态拉取覆盖。
 */
export const siteConfig = {
  /** 短标题 — 导航栏、logo、登录页 */
  title: '墨林百科',

  /** 副标题 — logo 下方、登录页、hero 区 */
  subtitle: '最智能的中国画与书法大库',

  /** 全称 — document.title 拼接用 */
  fullTitle: '墨林百科 - 最智能的中国画与书法大库',

  /** 域名 */
  domain: 'molin.wiki',

  /** 页脚文案 */
  footer: '墨林百科 © 2026',

  /** 作者 */
  author: '周豪 Zax',

  /** HTML <title> 默认值 */
  htmlTitle: '墨林百科 - 最智能的中国画与书法大库',
}

export default siteConfig
