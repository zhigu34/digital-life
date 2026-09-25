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
  const username = `ledger_${randomUUID().replaceAll('-', '').slice(0, 16)}`
  const created = await api.post('/api/admin/users', {
    headers: { 'X-CSRF-Token': session.csrf_token },
    data: { username, password, display_name: '记账体验员' },
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

/** The ledger page keeps its four sections behind an inner tab bar. */
async function tab(page: Page, name: '流水' | '账单' | '管理' | '报表') {
  await page.locator('.ledger-tabs').getByRole('button', { name, exact: true }).click()
  await expect(page.locator('.global-error')).toHaveCount(0)
}

async function addAccount(page: Page, name: string, opening: string) {
  await page.getByRole('button', { name: '添加账户', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('名称', { exact: true }).fill(name)
  await dialog.getByLabel(/^期初余额/).fill(opening)
  await dialog.getByRole('button', { name: '保存账户', exact: true }).click()
  await expect(dialog).toHaveCount(0)
  await expect(card(page, name)).toBeVisible()
}

function card(page: Page, name: string) {
  return page.locator('.account-card').filter({ hasText: name })
}

/** Local calendar date, matching what the date input expects. */
function localToday() {
  return new Date().toLocaleDateString('sv-SE')
}

test('ledger entries derive account balances and account filtering', async ({ page }) => {
  await login(page, await account())
  await navigate(page, '记账')

  await tab(page, '管理')
  await addAccount(page, '招行储蓄卡', '1000')
  await addAccount(page, '微信零钱', '0')
  await expect(card(page, '招行储蓄卡')).toContainText('1,000.00')

  await tab(page, '流水')
  await page.getByRole('button', { name: '记一笔', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel(/^金额/).fill('25.50')
  await dialog.getByLabel(/^日期/).fill(localToday())
  await dialog.getByLabel(/^账户/).selectOption({ label: '招行储蓄卡（CNY）' })
  await dialog.getByLabel(/^分类/).selectOption({ label: '餐饮' })
  await dialog.getByLabel(/^商户/).fill('老张面馆')
  await dialog.getByRole('button', { name: '保存记录', exact: true }).click()
  await expect(dialog).toHaveCount(0)

  const row = page.locator('.ledger-row').filter({ hasText: '餐饮' })
  await expect(row).toBeVisible()
  await expect(row).toContainText('25.50')
  await expect(row).toContainText('老张面馆')

  // The balance is derived from entries, not stored, so it must move on reload.
  await tab(page, '管理')
  await expect(card(page, '招行储蓄卡')).toContainText('974.50')

  await card(page, '招行储蓄卡').getByRole('button', { name: '查看流水', exact: true }).click()
  await expect(page.locator('.filter-chip')).toContainText('招行储蓄卡')
  await expect(page.locator('.ledger-row').filter({ hasText: '餐饮' })).toBeVisible()
})

test('confirming a bound bill records an entry and moves the balance', async ({ page }) => {
  await login(page, await account())
  await navigate(page, '记账')

  await tab(page, '管理')
  await addAccount(page, '工资卡', '500')

  await tab(page, '账单')
  await page.locator('.bill-heading').getByRole('button', { name: '添加账单', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('名称', { exact: true }).fill('云存储订阅')
  await dialog.getByLabel(/^每期金额/).fill('30')
  await dialog.getByLabel(/^下次应付/).fill(localToday())
  await dialog.getByLabel(/^扣款账户/).selectOption({ label: '工资卡（CNY）' })
  await dialog.getByRole('button', { name: '保存账单', exact: true }).click()
  await expect(dialog).toHaveCount(0)

  const bill = page.locator('.bill-row').filter({ hasText: '云存储订阅' })
  await expect(bill).toContainText('扣款：工资卡')

  await bill.getByRole('button', { name: '确认本期已付', exact: true }).click()
  await expect(page.locator('.global-error')).toHaveCount(0)

  // The generated entry is linked back to the bill and carries its amount.
  await tab(page, '流水')
  const row = page.locator('.ledger-row').filter({ hasText: '30.00' })
  await expect(row).toBeVisible()
  await expect(row.locator('.bill-tag')).toHaveText('账单')

  await tab(page, '管理')
  await expect(card(page, '工资卡')).toContainText('470.00')
})

test('an unbound bill only advances the due date', async ({ page }) => {
  await login(page, await account())
  await navigate(page, '记账')

  await tab(page, '账单')
  await page.locator('.bill-heading').getByRole('button', { name: '添加账单', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('名称', { exact: true }).fill('房租')
  await dialog.getByLabel(/^每期金额/).fill('2000')
  await dialog.getByLabel(/^下次应付/).fill(localToday())
  await dialog.getByRole('button', { name: '保存账单', exact: true }).click()
  await expect(dialog).toHaveCount(0)

  const bill = page.locator('.bill-row').filter({ hasText: '房租' })
  await expect(bill).toContainText('未绑定账户')
  const dueBefore = await bill.locator('.ledger-meta span').first().textContent()

  await bill.getByRole('button', { name: '确认本期已付', exact: true }).click()
  await expect(page.locator('.global-error')).toHaveCount(0)
  await expect(bill.locator('.ledger-meta span').first()).not.toHaveText(dueBefore ?? '')

  // No account was bound, so nothing should have been written to the ledger.
  await tab(page, '流水')
  await expect(page.getByText('还没有一笔流水')).toBeVisible()
})

test('the record shortcut opens the form only when it is used', async ({ page }) => {
  await login(page, await account())

  // Today's empty ledger offers a shortcut that should land on a blank form.
  await page.getByRole('button', { name: '去记账', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  await dialog.getByRole('button', { name: '取消', exact: true }).click()
  await expect(dialog).toHaveCount(0)

  // Coming back through the menu must not replay that one-shot request.
  await navigate(page, '追剧片单')
  await navigate(page, '记账')
  await expect(page.getByRole('dialog')).toHaveCount(0)
})
