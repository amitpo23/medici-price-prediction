param(
    [switch]$InstallBrowsers = $true,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

function Write-Step {
    param([string]$Message)
    Write-Host "[Playwright Setup] $Message" -ForegroundColor Cyan
}

function Test-Command {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Ensure-PackageScript {
    param(
        [string]$Name,
        [string]$Value
    )

    try {
        $existing = npm pkg get "scripts.$Name" 2>$null
        if ($existing -and $existing -match '"') {
            Write-Step "npm script '$Name' already exists"
            return
        }
    }
    catch {
    }

    Write-Step "Adding npm script '$Name'"
    npm pkg set "scripts.$Name=$Value" | Out-Null
}

Write-Step "Starting Playwright bootstrap in $PWD"

if (-not (Test-Command -Name 'node')) {
    throw "Node.js is not installed or not in PATH. Install from https://nodejs.org"
}

if (-not (Test-Command -Name 'npm')) {
    throw "npm is not installed or not in PATH. Install Node.js/npm first."
}

$nodeVersion = node -v
$npmVersion = npm -v
Write-Step "Detected Node.js $nodeVersion / npm $npmVersion"

$packageJsonPath = Join-Path $PWD 'package.json'
if (-not (Test-Path $packageJsonPath)) {
    Write-Step "No package.json found -> running npm init -y"
    npm init -y | Out-Null
}
else {
    Write-Step "Found existing package.json"
}

Write-Step "Installing @playwright/test as devDependency"
npm i -D @playwright/test

if ($InstallBrowsers) {
    Write-Step "Installing Playwright browsers"
    npx playwright install
}
else {
    Write-Step "Skipping browser installation (InstallBrowsers disabled)"
}

$playwrightConfigPath = Join-Path $PWD 'playwright.config.ts'
if ((-not (Test-Path $playwrightConfigPath)) -or $Force) {
    Write-Step "Creating playwright.config.ts"
    @"
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 30_000,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
"@ | Set-Content -Path $playwrightConfigPath -Encoding UTF8
}
else {
    Write-Step "playwright.config.ts already exists (use -Force to overwrite)"
}

$testsDir = Join-Path $PWD 'tests'
if (-not (Test-Path $testsDir)) {
    New-Item -ItemType Directory -Path $testsDir | Out-Null
}

$smokePath = Join-Path $testsDir 'smoke.spec.ts'
if ((-not (Test-Path $smokePath)) -or $Force) {
    Write-Step "Creating tests/smoke.spec.ts"
    @"
import { test, expect } from '@playwright/test';

test('smoke: playwright is working', async ({ page }) => {
  await page.goto('https://example.com');
  await expect(page).toHaveTitle(/Example/);
});
"@ | Set-Content -Path $smokePath -Encoding UTF8
}
else {
    Write-Step "tests/smoke.spec.ts already exists (use -Force to overwrite)"
}

Ensure-PackageScript -Name 'test:e2e' -Value 'playwright test'
Ensure-PackageScript -Name 'test:e2e:ui' -Value 'playwright test --ui'
Ensure-PackageScript -Name 'test:e2e:headed' -Value 'playwright test --headed'

Write-Step "Setup completed successfully"
Write-Host "Run: npm run test:e2e" -ForegroundColor Green
