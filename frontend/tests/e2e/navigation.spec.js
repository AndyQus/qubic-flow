/**
 * E2E tests — Navigation between pages
 */
import { test, expect } from '@playwright/test'

test.describe('Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('can navigate to Wallets page', async ({ page }) => {
    await page.click('a[href*="wallet"], nav >> text=Wallets')
    await expect(page).toHaveURL(/wallet/)
    await expect(page.locator('h1, [class*="title"]').first()).toBeVisible()
  })

  test('can navigate to Settings page', async ({ page }) => {
    await page.click('a[href*="setting"], nav >> text=Settings, nav >> text=Einstellungen')
    await expect(page).toHaveURL(/setting/)
  })

  test('can navigate to Nodes page', async ({ page }) => {
    await page.click('a[href*="node"], nav >> text=Nodes')
    await expect(page).toHaveURL(/node/)
  })

  test('can navigate back to Dashboard from Wallets', async ({ page }) => {
    await page.goto('/wallets')
    await page.click('a[href="/"], nav >> text=Dashboard')
    await expect(page).toHaveURL(/\/$|\/dashboard/)
  })
})

test.describe('Settings tabs', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/settings')
  })

  test('Display tab is active by default', async ({ page }) => {
    await expect(page.locator('[class*="tab-btn-active"]').first()).toContainText(/Display|Darstellung/)
  })

  test('can switch to Tax tab', async ({ page }) => {
    await page.click('button:has-text("Tax"), button:has-text("Steuer")')
    await expect(page.url()).toContain('tab=tax')
  })

  test('can switch to Data tab', async ({ page }) => {
    await page.click('button:has-text("Data"), button:has-text("Daten")')
    await expect(page.url()).toContain('tab=data')
  })

  test('tab state persists on reload', async ({ page }) => {
    await page.click('button:has-text("Tax"), button:has-text("Steuer")')
    await page.reload()
    await expect(page.locator('[class*="tab-btn-active"]').first()).toContainText(/Tax|Steuer/)
  })
})
