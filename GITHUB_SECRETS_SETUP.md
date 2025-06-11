# GitHub Secrets Setup Guide

This guide explains how to set up GitHub Secrets for automated package distribution.

## Required Secrets

### 1. CHOCOLATEY_API_KEY

This secret is needed to automatically publish packages to Chocolatey.org during releases.

#### Steps to set up:

1. **Get your Chocolatey API Key:**
   - Go to [chocolatey.org/account](https://chocolatey.org/account)
   - Log in with your account
   - Click on "API Keys" in the left sidebar
   - Copy your API key (it looks like: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)

2. **Add to GitHub Secrets:**
   - Go to your repository: [https://github.com/alexbigkid/eir](https://github.com/alexbigkid/eir)
   - Click **Settings** (in the repository tabs)
   - Click **Secrets and variables** → **Actions** (in the left sidebar)
   - Click **New repository secret**
   - Set **Name**: `CHOCOLATEY_API_KEY`
   - Set **Secret**: Paste your API key from step 1
   - Click **Add secret**

## How It Works

### Automated Distribution Process

When you create a release tag (`git tag patch && git push origin patch`), GitHub Actions will:

1. **Build binaries** for all platforms (Linux x64/ARM64, Windows x64, macOS Universal)
2. **Create packages** (.deb, .nupkg, Homebrew formula)
3. **Publish automatically:**
   - **Homebrew**: Updates the `homebrew-eir` repository with new formula
   - **APT**: Updates GitHub Pages with new repository metadata
   - **Chocolatey**: Uploads .nupkg file to chocolatey.org (if API key is set)

### Security Features

- **API key is encrypted**: GitHub Secrets are encrypted and only available to your workflows
- **Conditional publishing**: Chocolatey publishing only happens if the secret is set
- **No local storage**: API key never touches your local machine or gets committed to git

## Verification

After setting up the secret, you can verify it's working by:

1. **Check secret exists:**
   - Go to repository **Settings** → **Secrets and variables** → **Actions**
   - You should see `CHOCOLATEY_API_KEY` listed (value will be hidden)

2. **Test with a release:**
   - Create a test release: `git tag patch && git push origin patch`
   - Watch the GitHub Actions workflow
   - Check the "Publish to Chocolatey" step in the logs

## Optional: GitHub Pages Setup

For APT repository hosting, enable GitHub Pages:

1. Go to repository **Settings** → **Pages**
2. Under **Source**, select **GitHub Actions**
3. Your APT repository will be available at: `https://alexbigkid.github.io/eir/apt-repo`

## Troubleshooting

### Chocolatey Publishing Fails
- Verify your API key is correct in GitHub Secrets
- Check that your chocolatey.org account has publishing permissions
- Review the GitHub Actions logs for specific error messages

### Homebrew Update Fails
- Ensure the `homebrew-eir` repository exists and is public
- Check that GitHub Actions has access to push to the repository

### APT Repository Issues
- Verify GitHub Pages is enabled in repository settings
- Check that the workflow successfully commits to the `docs/` directory

## Current Status

✅ **GitHub Actions**: Configured for automated publishing  
🔄 **Chocolatey Secret**: Add your API key to GitHub Secrets  
🔄 **GitHub Pages**: Enable in repository settings for APT hosting  
✅ **Homebrew Tap**: Ready (homebrew-eir repository created)  

The complete automated release pipeline is ready once you add the Chocolatey API key!