import { test, expect, request, type Page } from '@playwright/test'
import { randomUUID } from 'node:crypto'
import { writeFileSync } from 'node:fs'

const baseURL = process.env.E2E_BASE_URL || 'http://127.0.0.1:5173'
const password = 'Only-for-browser-tests-2026!'
test.beforeEach(async ({ page }) => { page.on('dialog', dialog => dialog.accept()) })
async function account() {
  const api = await request.newContext({ baseURL, extraHTTPHeaders: { Origin: baseURL } })
  const login = await api.post('/api/auth/login', { data: {
    username: process.env.E2E_ADMIN_USERNAME || 'ciadmin',
    password: process.env.E2E_ADMIN_PASSWORD || 'ci-only-test-password-2026',
  } })
  expect(login.status(), await login.text()).toBe(200)
  const session = await login.json()
  const username = `test_${randomUUID().replaceAll('-', '').slice(0, 16)}`
  const created = await api.post('/api/admin/users', { headers: { 'X-CSRF-Token': session.csrf_token },
    data: { username, password, display_name: '生活体验员' } })
  expect(created.status(), await created.text()).toBe(201)
  await api.dispose()
  return username
}
async function login(page: Page, username: string, secret = password) {
  await page.goto('/')
  await page.getByLabel('用户名', { exact: true }).fill(username)
  await page.getByLabel('密码', { exact: true }).fill(secret)
  await page.getByRole('button', { name: '进入我的空间' }).click()
  await expect(page.getByRole('main')).toBeVisible()
  await expect(page.getByRole('status', { name: '正在同步记录' })).toHaveCount(0)
}
async function navigate(page: Page, name: string) {
  await page.getByRole('button', { name, exact: true }).filter({ visible: true }).first().click()
}
async function add(page: Page, button: string, title: string) {
  await page.getByRole('button', { name: button, exact: true }).first().click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  await dialog.getByLabel('名称', { exact: true }).fill(title)
  return dialog
}
async function save(page: Page) {
  await page.getByRole('dialog').getByRole('button', { name: '保存记录', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
}

test('task lifecycle, profile and layout work on each device', async ({ page }, testInfo) => {
  await login(page, await account())
  await navigate(page, '待办清单')
  let form = await add(page, '添加待办', '读完一本好书')
  await form.getByRole('combobox', { name: '状态', exact: true }).selectOption('doing')
  await form.getByRole('combobox', { name: '优先级', exact: true }).selectOption('high')
  await form.getByLabel('备注').fill('每天留一点时间给自己')
  await save(page)
  await expect(page.getByRole('heading', { name: '读完一本好书', exact: true })).toBeVisible()
  await page.getByRole('button', { name: '编辑 读完一本好书', exact: true }).click()
  await page.getByRole('dialog').getByLabel('名称', { exact: true }).fill('读完一本好书，并写下感想')
  await save(page)
  await page.getByRole('button', { name: '完成 读完一本好书，并写下感想', exact: true }).click()
  await expect(page.getByRole('button', { name: '重新打开 读完一本好书，并写下感想' })).toBeVisible()
  await navigate(page, '个人设置')
  await page.getByLabel('显示名称', { exact: true }).fill('认真生活的人')
  await page.getByLabel('生日').fill('1995-07-09')
  await page.getByRole('combobox', { name: '时区', exact: true }).fill('Factory')
  await page.getByRole('button', { name: '保存个人资料', exact: true }).click()
  await expect(page.getByText('请选择当前浏览器支持的时区，例如 Asia/Shanghai 或 UTC', { exact: true })).toBeVisible()
  await page.getByRole('combobox', { name: '时区', exact: true }).fill('Asia/Shanghai')
  await page.getByRole('button', { name: '保存个人资料', exact: true }).click()
  await expect(page.getByText('个人资料已保存', { exact: true })).toBeVisible()
  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: '导出我的数据', exact: true }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toMatch(/^digital-life-.*\.json$/)
  await navigate(page, '今日总览')
  await expect(page.locator('main')).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('dashboard.png'), fullPage: true })
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)
  expect(overflow).toBe(false)
  await navigate(page, '待办清单')
  await page.getByRole('button', { name: '删除 读完一本好书，并写下感想', exact: true }).click()
  await expect(page.getByRole('heading', { name: '读完一本好书，并写下感想', exact: true })).toHaveCount(0)
})

test('expenses, shows and milestones persist through reload', async ({ page }, testInfo) => {
  await login(page, await account())
  await navigate(page, '周期费用')
  let form = await add(page, '添加费用', '云存储年费')
  await form.getByLabel('每期金额', { exact: true }).fill('120')
  await form.getByRole('combobox', { name: '付费周期', exact: true }).selectOption('12')
  await form.getByLabel('下次应付', { exact: true }).fill('2027-01-31')
  await save(page)
  await page.getByRole('button', { name: '确认本期已付' }).click()
  await expect(page.getByText('2028.01.31')).toBeVisible()
  await navigate(page, '追剧片单')
  form = await add(page, '添加作品', '周末的好故事')
  await form.getByRole('combobox', { name: '类型', exact: true }).selectOption('anime')
  await form.getByLabel('总集数').fill('2')
  await save(page)
  await page.getByRole('button', { name: '看完一集' }).click()
  await expect(page.getByText('已看 1', { exact: false })).toBeVisible()
  await page.getByRole('button', { name: '看完一集' }).click()
  await expect(page.getByRole('button', { name: '看完一集' })).toBeDisabled()
  await navigate(page, '重要日子')
  form = await add(page, '添加日子', '开始记录生活的日子')
  await form.getByLabel('日期', { exact: true }).fill('2026-09-14')
  await form.getByLabel('每年纪念这个日子').check()
  await save(page)
  await page.reload()
  await navigate(page, '重要日子')
  await expect(page.getByRole('heading', { name: '开始记录生活的日子', exact: true })).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('milestones.png'), fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)).toBe(false)
})

test('another login cannot see the previous account records', async ({ page }) => {
  const alice = await account(), bob = await account()
  await login(page, alice)
  await navigate(page, '待办清单')
  await add(page, '添加待办', '只属于第一个账号的记录')
  await save(page)
  // Expire the old session on the server, then load the login screen in the same browser.
  await page.evaluate(async () => {
    const session = await fetch('/api/auth/session').then(r => r.json())
    const response = await fetch('/api/auth/logout', { method: 'POST', headers: { 'X-CSRF-Token': session.csrf_token } })
    if (!response.ok) throw new Error('Logout failed')
  })
  await login(page, bob)
  await navigate(page, '待办清单')
  await expect(page.getByText('只属于第一个账号的记录', { exact: true })).toHaveCount(0)
  await expect(page.getByText('从一件小事开始', { exact: true })).toBeVisible()
})

test('administrator can create an independent account through the interface', async ({ page }) => {
  await login(page, process.env.E2E_ADMIN_USERNAME || 'ciadmin', process.env.E2E_ADMIN_PASSWORD || 'ci-only-test-password-2026')
  await navigate(page, '账号管理')
  await page.getByRole('button', { name: '创建账户', exact: true }).click()
  const form = page.getByRole('dialog')
  const suffix = randomUUID().replaceAll('-', '').slice(0, 12)
  await form.getByLabel('用户名', { exact: true }).fill(`ui_${suffix}`)
  await form.getByLabel('显示名称', { exact: true }).fill(`新朋友${suffix}`)
  await form.getByLabel('初始密码', { exact: true }).fill(password)
  await form.getByRole('button', { name: '确认保存', exact: true }).click()
  await expect(form).toHaveCount(0)
  await expect(page.getByRole('heading', { name: `新朋友${suffix}`, exact: false })).toBeVisible()
  await navigate(page, '个人设置')
  await page.getByRole('button', { name: '退出登录', exact: true }).filter({ visible: true }).first().click()
  await login(page, `ui_${suffix}`)
  await expect(page.getByRole('button', { name: '账号管理', exact: true })).toHaveCount(0)
  await navigate(page, '待办清单')
  await expect(page.getByRole('heading', { name: '从一件小事开始', exact: true })).toBeVisible()
})

test('calendar gathers deadlines, dues and yearly milestones in one view', async ({ page }, testInfo) => {
  await login(page, await account())
  // The default profile timezone is Asia/Shanghai; derive the month the same
  // way so the calendar under test opens on the month these dates land in.
  const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai' }).format(new Date())
  const year = today.slice(0, 4), month = today.slice(5, 7)
  const iso = (day: number) => `${year}-${month}-${String(day).padStart(2, '0')}`
  const dayOfMonth = String(Number(today.slice(8)))
  await navigate(page, '待办清单')
  let form = await add(page, '添加待办', '月底前整理相册')
  await form.getByLabel('截止日期', { exact: false }).fill(iso(25))
  await save(page)
  await navigate(page, '周期费用')
  form = await add(page, '添加费用', '家庭云盘')
  await form.getByLabel('每期金额', { exact: true }).fill('30')
  await form.getByLabel('下次应付', { exact: false }).fill(iso(18))
  await save(page)
  await navigate(page, '重要日子')
  form = await add(page, '添加日子', '领证纪念日')
  await form.getByLabel('日期', { exact: true }).fill(`${Number(year) - 2}-${month}-21`)
  await form.getByLabel('每年纪念这个日子').check()
  await save(page)
  await navigate(page, '日历')
  const day18 = page.getByRole('button', { name: `查看 ${iso(18)} 的安排`, exact: true })
  const day21 = page.getByRole('button', { name: `查看 ${iso(21)} 的安排`, exact: true })
  await expect(day18).toContainText('家庭云盘')
  await expect(day21).toContainText('领证纪念日')
  await day18.click()
  await expect(page.getByRole('region', { name: '当日安排' })).toContainText('¥30.00')
  await page.locator('.calendar-event-row').first().click()
  await expect(page.getByText('家庭云盘', { exact: true })).toBeVisible()
  await navigate(page, '日历')
  await page.getByRole('button', { name: '下一个月', exact: true }).click()
  await expect(day18).toHaveCount(0)
  await page.getByRole('button', { name: '今天', exact: true }).click()
  await expect(day18).toContainText('家庭云盘')
  await expect(page.getByRole('region', { name: '当日安排' })).toContainText(`${dayOfMonth}日`)
  await page.screenshot({ path: testInfo.outputPath('calendar.png'), fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)).toBe(false)
})

test('statistics panels summarize expenses, maintenance costs and shows', async ({ page }, testInfo) => {
  await login(page, await account())
  const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai' }).format(new Date())
  await navigate(page, '周期费用')
  let form = await add(page, '添加费用', '家庭云盘')
  await form.getByLabel('每期金额', { exact: true }).fill('30')
  await form.getByLabel('下次应付', { exact: false }).fill(`${today.slice(0, 7)}-18`)
  await save(page)
  const trend = page.getByRole('region', { name: '近十二个月应付趋势' })
  await expect(trend).toBeVisible()
  await expect(trend).toContainText('¥30.00')
  await expect(trend.locator('.bar-col')).toHaveCount(12)
  await navigate(page, '周期维护')
  form = await add(page, '添加维护', '净水器前置滤芯')
  await form.getByLabel('上次完成日期', { exact: true }).fill(`${today.slice(0, 7)}-01`)
  await form.getByRole('button', { name: '保存维护', exact: true }).click()
  await expect(form).toHaveCount(0)
  await page.getByRole('button', { name: '记录完成', exact: true }).click()
  form = page.getByRole('dialog')
  await form.getByLabel('费用').fill('66.60')
  await form.getByRole('button', { name: '确认完成', exact: true }).click()
  await expect(form).toHaveCount(0)
  const costs = page.getByRole('region', { name: '近十二个月维护费用' })
  await expect(costs).toBeVisible()
  await expect(costs).toContainText('¥66.60')
  await expect(costs.locator('.bar-col')).toHaveCount(12)
  await navigate(page, '追剧片单')
  form = await add(page, '添加作品', '统计用的一部作品')
  await form.getByLabel('总集数').fill('12')
  await save(page)
  const showsStats = page.getByRole('region', { name: '追剧统计' })
  await expect(showsStats).toBeVisible()
  await expect(showsStats.locator('.summary-card').filter({ hasText: '想看' })).toContainText('1')
  await expect(showsStats.locator('.summary-card').filter({ hasText: '累计看完' })).toContainText('0')
  await page.screenshot({ path: testInfo.outputPath('stats.png'), fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)).toBe(false)
})

test('profile import restores an export into a fresh account', async ({ page }, testInfo) => {
  const source = await account()
  const api = await request.newContext({ baseURL, extraHTTPHeaders: { Origin: baseURL } })
  const sessionResponse = await api.post('/api/auth/login', { data: { username: source, password } })
  const session = await sessionResponse.json()
  const created = await api.post('/api/tasks', {
    headers: { 'X-CSRF-Token': session.csrf_token },
    data: { title: '搬家用的待办', priority: 'high' },
  })
  expect(created.status(), await created.text()).toBe(201)
  const exportData = await (await api.get('/api/export')).json()
  expect(exportData.tasks).toHaveLength(1)
  await api.dispose()
  const file = testInfo.outputPath('export.json')
  writeFileSync(file, JSON.stringify(exportData))
  await login(page, await account())
  await navigate(page, '待办清单')
  await add(page, '添加待办', '会被替换的旧待办')
  await save(page)
  await navigate(page, '个人设置')
  await page.getByLabel('选择要导入的 JSON 文件').setInputFiles(file)
  const dialog = page.getByRole('dialog')
  await expect(dialog).toContainText('待办 1')
  await dialog.getByRole('button', { name: '替换并导入', exact: true }).click()
  await expect(page.getByText('已导入 1 条记录', { exact: true })).toBeVisible()
  await navigate(page, '待办清单')
  await expect(page.getByRole('heading', { name: '搬家用的待办', exact: true })).toBeVisible()
  await expect(page.getByText('会被替换的旧待办', { exact: true })).toHaveCount(0)
})

test('quick notes keep private daily entries with search', async ({ page }) => {
  const alice = await account(), bob = await account()
  await login(page, alice)
  await navigate(page, '文字随记')
  await page.getByRole('button', { name: '写一条', exact: true }).first().click()
  let dialog = page.getByRole('dialog')
  await dialog.getByLabel('内容', { exact: false }).fill('今天的晚霞很好看，记下来。')
  await dialog.getByRole('button', { name: '记下这一刻' }).click()
  await expect(dialog).toHaveCount(0)
  await expect(page.getByText('今天的晚霞很好看，记下来。', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '编辑随记', exact: true }).click()
  dialog = page.getByRole('dialog')
  await dialog.getByLabel('内容', { exact: false }).fill('今天的晚霞特别好看。')
  await dialog.getByRole('button', { name: '保存修改' }).click()
  await expect(dialog).toHaveCount(0)
  await expect(page.getByText('今天的晚霞特别好看。', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '写一条', exact: true }).first().click()
  dialog = page.getByRole('dialog')
  await dialog.getByLabel('内容', { exact: false }).fill('健身房练了背，明天会酸。')
  await dialog.getByRole('button', { name: '记下这一刻' }).click()
  await expect(dialog).toHaveCount(0)
  await page.getByLabel('搜索随记').fill('晚霞')
  await expect(page.getByText('健身房练了背，明天会酸。', { exact: true })).toHaveCount(0)
  await expect(page.getByText('今天的晚霞特别好看。', { exact: true })).toBeVisible()
  await page.getByLabel('搜索随记').fill('')
  await page.reload()
  await navigate(page, '文字随记')
  await expect(page.getByText('今天的晚霞特别好看。', { exact: true })).toBeVisible()
  await navigate(page, '个人设置')
  await page.getByRole('button', { name: '退出登录', exact: true }).filter({ visible: true }).first().click()
  await login(page, bob)
  await navigate(page, '文字随记')
  await expect(page.getByText('今天的晚霞特别好看。', { exact: true })).toHaveCount(0)
  await expect(page.getByRole('heading', { name: '把此刻写下来', exact: true })).toBeVisible()
})

test('metadata search fills title and episode count for anime and drama', async ({ page }) => {
  await login(page, await account())
  const fixtures: Record<string, object> = {
    芙莉莲: {
      results: [
        {
          source: 'bangumi',
          source_id: 400602,
          title: '葬送的芙莉莲',
          original_title: '葬送のフリーレン',
          air_date: '2023-09-29',
          total_episodes: 28,
          platform: 'TV',
        },
      ],
    },
    漫长的季节: {
      results: [
        {
          source: 'bangumi',
          source_id: 396646,
          title: '漫长的季节',
          original_title: '漫长的季节',
          air_date: '2023-04-22',
          total_episodes: 12,
          platform: '华语剧',
        },
      ],
    },
  }
  await page.route('**/api/shows/metadata**', async (route) => {
    const url = new URL(route.request().url())
    const keyword = url.searchParams.get('keyword') ?? ''
    const fixture = Object.entries(fixtures).find(([needle]) => keyword.includes(needle))
    if (!fixture) {
      await route.fallback()
      return
    }
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(fixture[1]) })
  })
  await navigate(page, '追剧片单')
  await page.getByRole('button', { name: '添加作品', exact: true }).first().click()
  const dialog = page.getByRole('dialog')
  await dialog.getByRole('combobox', { name: '类型', exact: true }).selectOption('anime')
  await dialog.getByLabel('名称', { exact: true }).fill('芙莉莲')
  await dialog.getByRole('button', { name: '联网搜索动漫信息' }).click()
  await dialog.getByRole('button', { name: /葬送的芙莉莲/ }).click()
  await expect(dialog.getByLabel('名称', { exact: true })).toHaveValue('葬送的芙莉莲')
  await expect(dialog.getByLabel('总集数', { exact: false })).toHaveValue('28')
  await save(page)
  await expect(page.getByRole('heading', { name: '葬送的芙莉莲', exact: true })).toBeVisible()
  // Real-person dramas use the same flow through the TV media type.
  await page.getByRole('button', { name: '添加作品', exact: true }).first().click()
  await dialog.getByRole('combobox', { name: '类型', exact: true }).selectOption('tv')
  await dialog.getByLabel('名称', { exact: true }).fill('漫长的季节')
  await dialog.getByRole('button', { name: '联网搜索剧集信息' }).click()
  await dialog.getByRole('button', { name: /漫长的季节/ }).click()
  await expect(dialog.getByLabel('名称', { exact: true })).toHaveValue('漫长的季节')
  await expect(dialog.getByLabel('总集数', { exact: false })).toHaveValue('12')
  await save(page)
  await expect(page.getByRole('heading', { name: '漫长的季节', exact: true })).toBeVisible()
  await page.unroute('**/api/shows/metadata**')
})

test('recurring maintenance tracks completion, corrections, reminders and private history', async ({ page }, testInfo) => {
  const alice = await account(), bob = await account()
  await login(page, alice)
  await navigate(page, '周期维护')
  let form = await add(page, '添加维护', '净水器滤芯')
  await form.getByLabel('上次完成日期', { exact: true }).fill('2000-01-31')
  await form.getByLabel('周期数值', { exact: true }).fill('1')
  await form.getByRole('combobox', { name: '周期单位', exact: true }).selectOption('months')
  await form.getByLabel('提前提醒天数', { exact: true }).fill('14')
  await form.getByRole('button', { name: '保存维护', exact: true }).click()
  await expect(form).toHaveCount(0)
  const card = page.getByRole('article').filter({ has: page.getByRole('heading', { name: '净水器滤芯', exact: true }) })
  await expect(card).toContainText('2000-02-29')
  await expect(card).toContainText('逾期')
  await navigate(page, '今日总览')
  await expect(page.getByText('净水器滤芯', { exact: true })).toBeVisible()
  await navigate(page, '周期维护')
  await card.getByRole('button', { name: '记录完成', exact: true }).click()
  form = page.getByRole('dialog')
  await form.getByLabel('完成日期', { exact: true }).fill('2000-01-31')
  await form.getByRole('button', { name: '确认完成', exact: true }).click()
  await expect(form.getByRole('alert')).toBeVisible()
  await form.getByLabel('完成日期', { exact: true }).fill('2000-03-31')
  await form.getByLabel('费用').fill('129.50')
  await form.getByLabel('完成备注').fill('更换了 PP 棉滤芯')
  await form.getByRole('button', { name: '确认完成', exact: true }).click()
  await expect(form).toHaveCount(0)
  await expect(card).toContainText('2000-04-30')
  await card.getByRole('button', { name: '查看历史', exact: true }).click()
  form = page.getByRole('dialog')
  await expect(form).toContainText('更换了 PP 棉滤芯')
  await expect(form).toContainText('129.50')
  await form.getByRole('button', { name: '修正记录', exact: true }).first().click()
  await form.getByLabel('完成日期', { exact: true }).fill('2000-03-15')
  await form.getByLabel('费用').fill('99')
  await form.getByRole('button', { name: '保存修正', exact: true }).click()
  await expect(form).toContainText('99.00')
  await form.getByRole('button', { name: '关闭', exact: true }).click()
  await expect(card).toContainText('2000-04-15')
  await page.reload()
  await navigate(page, '周期维护')
  await expect(card).toContainText('2000-04-15')
  await page.screenshot({ path: testInfo.outputPath('maintenance.png'), fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)).toBe(false)
  await page.getByRole('button', { name: '编辑维护 净水器滤芯', exact: true }).click()
  form = page.getByRole('dialog')
  await form.getByRole('checkbox').uncheck()
  await form.getByRole('button', { name: '保存维护', exact: true }).click()
  await expect(form).toHaveCount(0)
  await navigate(page, '今日总览')
  await expect(page.getByText('净水器滤芯', { exact: true })).toHaveCount(0)
  await navigate(page, '周期维护')
  let releaseDelete!: () => void
  let deleteSeen!: () => void
  const deleteRequest = new Promise<void>(resolve => { deleteSeen = resolve })
  const allowDelete = new Promise<void>(resolve => { releaseDelete = resolve })
  await page.route('**/api/maintenance/*', async route => {
    if (route.request().method() !== 'DELETE') return route.continue()
    deleteSeen()
    await allowDelete
    await route.continue()
  })
  const deletion = page.getByRole('button', { name: '删除维护 净水器滤芯', exact: true }).click()
  await deleteRequest
  await navigate(page, '今日总览')
  releaseDelete()
  await deletion
  await navigate(page, '周期维护')
  await expect(page.getByText('净水器滤芯', { exact: true })).toHaveCount(0)
  await page.unroute('**/api/maintenance/*')
  await navigate(page, '个人设置')
  await page.getByRole('button', { name: '退出登录', exact: true }).filter({ visible: true }).first().click()
  await login(page, bob)
  await navigate(page, '周期维护')
  await expect(page.getByText('净水器滤芯', { exact: true })).toHaveCount(0)
})
