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

async function addShow(page: Page, title: string, status = 'planned', mediaType = 'tv') {
  await page.getByRole('button', { name: '添加作品', exact: true }).first().click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('名称', { exact: true }).fill(title)
  await dialog.getByRole('combobox', { name: '类型', exact: true }).selectOption(mediaType)
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
  await expect(page.getByRole('dialog').getByRole('button', { name: /联网搜索剧集信息/ })).toBeVisible()
})

test('show editor exposes richer metadata and adapts movie fields', async ({ page }) => {
  await login(page, await account())
  await navigate(page, '追剧片单')

  await page.getByRole('button', { name: '添加作品', exact: true }).first().click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('名称', { exact: true }).fill('带资料的电影')
  await dialog.getByRole('combobox', { name: '类型', exact: true }).selectOption('movie')

  await expect(dialog.getByLabel('上映年份', { exact: true })).toBeVisible()
  await expect(dialog.getByLabel('引用链接', { exact: true })).toBeVisible()
  await expect(dialog.getByLabel('已看集数', { exact: true })).toHaveCount(0)
  await expect(dialog.getByLabel('总集数', { exact: true })).toHaveCount(0)
  await expect(dialog.getByLabel('更新日', { exact: true })).toHaveCount(0)
  await expect(dialog.getByLabel('季数', { exact: true })).toHaveCount(0)

  await dialog.getByLabel('上映年份', { exact: true }).fill('2024')
  await dialog.getByLabel('引用链接', { exact: true }).fill('https://www.themoviedb.org/movie/42')
  await dialog.getByRole('combobox', { name: '状态', exact: true }).selectOption('completed')
  await expect(dialog.getByLabel('看完日期', { exact: true })).not.toHaveValue('')
  await dialog.getByRole('button', { name: '保存记录', exact: true }).click()
  await expect(dialog).toHaveCount(0)

  const titleLink = page.getByRole('link', { name: '带资料的电影', exact: true })
  await expect(titleLink).toHaveAttribute('href', 'https://www.themoviedb.org/movie/42')
  await expect(titleLink).toHaveAttribute('target', '_blank')
  await expect(page.getByText('2024', { exact: true }).first()).toBeVisible()
})

test('shows are grouped by type and movie cards omit episode controls', async ({ page }) => {
  await login(page, await account())
  await navigate(page, '追剧片单')

  await addShow(page, '分组剧集', 'watching', 'tv')
  await addShow(page, '分组动漫', 'watching', 'anime')
  await addShow(page, '分组电影', 'planned', 'movie')

  await expect(page.getByRole('heading', { name: /剧集/ }).first()).toBeVisible()
  await expect(page.getByRole('heading', { name: /动漫/ }).first()).toBeVisible()
  await expect(page.getByRole('heading', { name: /电影/ }).first()).toBeVisible()

  const movieCard = page.locator('article').filter({ hasText: '分组电影' })
  const tvCard = page.locator('article').filter({ hasText: '分组剧集' })
  await expect(movieCard.getByRole('button', { name: /\+1 集|看完一集/ })).toHaveCount(0)
  await expect(tvCard.getByRole('button', { name: /\+1 集|看完一集/ })).toBeVisible()

  await page.getByRole('button', { name: '在看', exact: true }).click()
  await expect(page.getByText('分组电影', { exact: true })).toHaveCount(0)
  await expect(page.getByText('分组剧集', { exact: true })).toBeVisible()
  await expect(page.getByText('分组动漫', { exact: true })).toBeVisible()
})
