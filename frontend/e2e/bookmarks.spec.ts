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
  const username = `bm_${randomUUID().replaceAll('-', '').slice(0, 16)}`
  const created = await api.post('/api/admin/users', {
    headers: { 'X-CSRF-Token': session.csrf_token },
    data: { username, password, display_name: '书签体验员' },
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
  await page.getByRole('navigation', { name: '更多页面' }).getByRole('button', { name, exact: true }).click()
}

async function addBookmark(
  page: Page,
  url: string,
  title: string,
  folder = '',
  note = '',
  starred = false,
) {
  await page.getByRole('button', { name: '添加书签', exact: true }).first().click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('网址', { exact: true }).fill(url)
  await dialog.getByLabel('标题', { exact: true }).fill(title)
  if (folder) await dialog.getByLabel('分组', { exact: true }).fill(folder)
  if (note) await dialog.getByLabel(/^备注/).fill(note)
  if (starred) await dialog.getByLabel('置顶收藏', { exact: true }).check()
  await dialog.getByRole('button', { name: '保存书签', exact: true }).click()
  await expect(dialog).toHaveCount(0)
}

test('bookmarks are created, grouped and opened in a new tab', async ({ page }) => {
  await login(page, await account())
  await navigate(page, '书签')

  await expect(page.getByText('还没有收藏任何站点')).toBeVisible()
  await addBookmark(page, 'https://docs.example.com/guide', '团队文档', '工作', '需要内网访问')
  await addBookmark(page, 'https://status.example.com', '服务状态页', '运维')

  await expect(page.getByRole('heading', { name: '工作', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: '运维', exact: true })).toBeVisible()
  await expect(page.getByText('docs.example.com', { exact: true })).toBeVisible()
  await expect(page.getByText('需要内网访问')).toBeVisible()

  const link = page.getByRole('link', { name: /团队文档/ })
  await expect(link).toHaveAttribute('href', 'https://docs.example.com/guide')
  await expect(link).toHaveAttribute('target', '_blank')
  await expect(link).toHaveAttribute('rel', 'noopener noreferrer')
})

test('bookmarks search and folder filter narrow the list', async ({ page }) => {
  await login(page, await account())
  await navigate(page, '书签')

  await addBookmark(page, 'https://panel.example.com', '服务器面板', '运维')
  await addBookmark(page, 'https://reader.example.net', 'RSS 阅读器')
  await addBookmark(page, 'https://hub.example.com', '镜像站', '运维')

  await page.getByLabel('搜索书签', { exact: true }).fill('reader')
  await expect(page.getByText('RSS 阅读器')).toBeVisible()
  await expect(page.getByText('服务器面板')).toHaveCount(0)

  await page.getByLabel('搜索书签', { exact: true }).fill('')
  await page.getByLabel('按分组筛选', { exact: true }).selectOption('运维')
  await expect(page.getByText('服务器面板')).toBeVisible()
  await expect(page.getByText('RSS 阅读器')).toHaveCount(0)

  await page.getByLabel('按分组筛选', { exact: true }).selectOption('__none__')
  await expect(page.getByText('RSS 阅读器')).toBeVisible()
  await expect(page.getByText('服务器面板')).toHaveCount(0)

  await page.getByLabel('按分组筛选', { exact: true }).selectOption('all')
  await expect(page.getByText('服务器面板')).toBeVisible()
  await expect(page.getByText('RSS 阅读器')).toBeVisible()
})

test('bookmark editing keeps the url and delete removes the card', async ({ page }) => {
  await login(page, await account())
  await navigate(page, '书签')

  await addBookmark(page, 'https://panel.example.com', '服务器面板', '运维')
  await page.getByRole('button', { name: '编辑 服务器面板', exact: true }).click()

  const dialog = page.getByRole('dialog')
  await expect(dialog.getByLabel('网址', { exact: true })).toHaveValue('https://panel.example.com')
  await expect(dialog.getByLabel('分组', { exact: true })).toHaveValue('运维')
  await expect(dialog.getByRole('button', { name: '获取标题', exact: true })).toBeVisible()
  await dialog.getByLabel('标题', { exact: true }).fill('面板首页')
  await dialog.getByRole('button', { name: '保存书签', exact: true }).click()
  await expect(dialog).toHaveCount(0)
  await expect(page.getByText('面板首页')).toBeVisible()

  await page.getByRole('button', { name: '编辑 面板首页', exact: true }).click()
  await page.getByRole('dialog').getByRole('button', { name: '删除', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(page.getByText('还没有收藏任何站点')).toBeVisible()
})

test('bookmark form rejects a non-http url', async ({ page }) => {
  await login(page, await account())
  await navigate(page, '书签')

  await page.getByRole('button', { name: '添加书签', exact: true }).first().click()
  const dialog = page.getByRole('dialog')
  // The browser blocks javascript: in href anyway; the server is the real guard.
  await dialog.getByLabel('网址', { exact: true }).fill('ftp://example.com/file')
  await dialog.getByLabel('标题', { exact: true }).fill('非法协议')
  await dialog.getByRole('button', { name: '保存书签', exact: true }).click()
  await expect(dialog.getByRole('alert')).toBeVisible()
})
