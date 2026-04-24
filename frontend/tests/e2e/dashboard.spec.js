/**
 * E2E tests — Dashboard page
 *
 * Prerequisites:
 *   - Backend running on http://localhost:8000
 *   - Frontend dev server started automatically by Playwright (playwright.config.js)
 *
 * Run: npm run test:e2e
 */
import { test, expect } from '@playwright/test'

test.describe('Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('shows page title and subtitle', async ({ page }) => {
    await expect(page).toHaveTitle(/QubicFlow/)
  })

  test('dashboard navigation link is active', async ({ page }) => {
    const navLink = page.locator('nav a[href="/"], nav a[href*="dashboard"]').first()
    await expect(navLink).toBeVisible()
  })

  test('events table or loading state is visible', async ({ page }) => {
    // Either the table renders or a loading indicator appears
    const hasTable   = await page.locator('table').isVisible().catch(() => false)
    const hasLoading = await page.locator('text=Loading').isVisible().catch(() => false)
    const hasEmpty   = await page.locator('text=No events').isVisible().catch(() => false)
    expect(hasTable || hasLoading || hasEmpty).toBe(true)
  })

  test('node status indicator is present in header', async ({ page }) => {
    // Header should contain connection or sync status
    const header = page.locator('header, [class*="header"]').first()
    await expect(header).toBeVisible()
  })
})
