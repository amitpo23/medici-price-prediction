#!/bin/bash
# Browser price check — runs every 8h via system crontab
# Crontab entry: 17 */8 * * * /Users/mymac/Desktop/coding/medici-price-prediction/scripts/run_scan.sh

/Users/mymac/.nvm/versions/node/v22.22.0/bin/node /Users/mymac/Desktop/coding/medici-price-prediction/scripts/browser_scan.js --no-db >> /tmp/browser_scan.log 2>&1
