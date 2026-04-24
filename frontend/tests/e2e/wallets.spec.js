/**
 * E2E tests — Wallet management
 */
import { test, expect } from '@playwright/test'

test.describe('Wallets page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/wallets')
  })

  test('shows Wallets page heading', async ({ page }) => {
    await expect(page.locator('h1, [class*="title"]').first()).toBeVisible()
  })

  test('Add Wallet button is visible', async ({ page }) => {
    const addBtn = page.locator('button:has-text("Add Wallet"), button:has-text("Wallet hinzufügen")')
    await expect(addBtn).toBeVisible()
  })

  test('shows empty state message when no wallets configured', async ({ page }) => {
    // Either wallets are listed or the empty state message appears
    const hasWallets = await page.locator('table tbody tr').count() > 0
    if (!hasWallets) {
      await expect(page.locator('text=No wallets, text=Keine Wallets').first()).toBeVisible()
    }
  })

  test('wallet filter buttons are visible', async ({ page }) => {
    // Filter row should be present (All / Private / Business)
    const allFilter = page.locator('button:has-text("All"), button:has-text("Alle")').first()
    await expect(allFilter).toBeVisible()
  })
})

test.describe('Add wallet dialog', () => {
  test('opens add wallet form on button click', async ({ page }) => {
    await page.goto('/wallets')
    await page.click('button:has-text("Add Wallet"), button:has-text("Wallet hinzufügen")')
    // Form or modal should appear with an address input
    await expect(page.locator('input[placeholder*="Address"], input[placeholder*="Adresse"]').first()).toBeVisible()
  })

  test('shows validation error for duplicate address', async ({ page }) => {
    // This test requires at least one wallet to exist; skip gracefully if none
    await page.goto('/wallets')
    const walletRows = await page.locator('table tbody tr').count()
    if (walletRows === 0) {
      test.skip()
      return
    }
    // Open the add form and enter the same address
    await page.click('button:has-text("Add Wallet"), button:has-text("Wallet hinzufügen")')
    const firstAddr = await page.locator('table tbody tr td:first-child').first().textContent()
    if (firstAddr) {
      await page.fill('input[placeholder*="Address"], input[placeholder*="Adresse"]', firstAddr.trim())
      await page.click('button:has-text("Save"), button:has-text("Speichern")')
      await expect(page.locator('text=already exists, text=existiert bereits').first()).toBeVisible()
    }
  })
})
