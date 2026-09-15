import { test, expect, request, type Page } from '@playwright/test'
import { randomUUID } from 'node:crypto'

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
