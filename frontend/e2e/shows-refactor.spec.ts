import { test, expect, request, type Page } from '@playwright/test'
import { randomUUID } from 'node:crypto'

const baseURL = process.env.E2E_BASE_URL || 'http://127.0.0.1:5173'
const password = 'Only-for-browser-tests-2026!'

test.beforeEach(async ({ page }) => {
  page.on('dialog', dialog => dialog.accept())
})

async function account() {
  const api = await request.newContext({ baseURL, extraHTTPHeaders: { Origin: baseURL } })
  const login = await api.post('/api/auth/login', {
    data: {
      username: process.env.E2E_ADMIN_USERNAME || 'ciadmin',
      password: process.env.E2E_ADMIN_PASSWORD || 'ci-only-test-password-2026',
    },
  })
  expect(login.status(), await login.text()).toBe(200)
  const session = await login.json()
  const username = `shows_${randomUUID().replaceAll('-', '').slice(0, 16)}`
  const created = await api.post('/api/admin/users', {
    headers: { 'X-CSRF-Token': session.csrf_token },
    data: { username, password, display_name: '追剧体验员' },
  })
  expect(created.status(), await created.text()).toBe(201)
  await api.dispose()
  return username
}

async function login(page: Page, username: string) {
  await page.goto('/')
  await page.getByLabel('用户名', { exact: true }).fill(username)
  await page.getByLabel('密码', { exact: true }).fill(password)
  await page.getByRole('button', { name: '进入我的空间' }).click()
  await expect(page.getByRole('main')).toBeVisible()
  await expect(page.getByRole('status', { name: '正在同步记录' })).toHaveCount(0)
}

async function navigate(page: Page, name: string) {
  const direct = page.getByRole('button', { name, exact: true }).filter({ visible: true }).first()
  try {
    await direct.click({ timeout: 2500 })
    return
  } catch {
    // Mobile keeps secondary pages in the more sheet.
  }
  await page.getByRole('button', { name: '更多页面' }).click()
  await page
    .getByRole('navigation', { name: '更多页面' })
    .getByRole('button', { name, exact: true })
    .click()
}

async function addShow(page: Page, title: string, status = 'planned') {
  await page.getByRole('button', { name: '添加作品', exact: true }).first().click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('名称', { exact: true }).fill(title)
  await dialog.getByRole('combobox', { name: '状态', exact: true }).selectOption(status)
  await dialog.getByRole('button', { name: '保存记录', exact: true }).click()
  await expect(dialog).toHaveCount(0)
}

test('shows filtering, search and cover editing stay stable', async ({ page }) => {
  await login(page, await account())
  await navigate(page, '追剧片单')

  await addShow(page, '周末的好故事')
  await addShow(page, 'Breaking Bad', 'watching')

  await page.getByRole('button', { name: '在看', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Breaking Bad', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: '周末的好故事', exact: true })).toHaveCount(0)

  await page.getByRole('button', { name: '全部', exact: true }).click()
  await page.getByLabel('搜索记录', { exact: true }).fill('BREAKING')
  await expect(page.getByRole('heading', { name: 'Breaking Bad', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: '周末的好故事', exact: true })).toHaveCount(0)

  await page.getByLabel('搜索记录', { exact: true }).fill('周末')
  await page.getByRole('button', { name: '编辑 周末的好故事', exact: true }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByRole('dialog').getByLabel('名称', { exact: true })).toHaveValue('周末的好故事')
})
