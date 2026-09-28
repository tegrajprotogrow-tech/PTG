# Merchant Center: apply steps for 2026-09-28 (approved: P002, P007, P013)

Your live Shopify store is not changed by any of these steps.

## P007: Link the 2 supplemental feeds (about 5 minutes)
Sheets (owner: tegrajprotogrow@gmail.com):
- Titles: https://docs.google.com/spreadsheets/d/12nDSa0qaEuoCc1LYTZbNSAjGxSvIq2P9ezRJ092IIpg/edit
- Brand, Type & Labels: https://docs.google.com/spreadsheets/d/1ueCXep3whov23Dqe1RQDTiRpsVEL9D6ywC-AUPUnlgs/edit

For each sheet:
1. Merchant Center (5775540276) > **Settings > Data sources > Supplemental sources > Add supplemental product data**.
2. Choose **Google Sheets > Select an existing Google spreadsheet** and pick the sheet.
3. Fetch schedule: **Daily**. Link to the **Shopify primary source only**. Leave the PTG-* source unlinked.
4. Click **Create**, then **Fetch now**.
5. After about 1 hour, open Products and check a few items. The title should start with "Pro-To-Grow", the brand should be "Pro-To-Grow", and product_type should be filled in.

If the Merchant Center login isn't tegrajprotogrow@gmail.com, share both sheets with that login first (Viewer is enough).
**Rollback:** delete the supplemental source. Products go back to Shopify's values at the next fetch.

## P002: Remove duplicate listings
The PTG-* copies get 10–25 times the CTR of the Shopify copies. Keep the PTG copy where both exist:
1. Check each pair in `reports/2026-09-28_review.md` (P002 evidence). A few pairs are loose matches, for example PTG-BBO-300G-BOX matched to the 300g *Jar*. Skip any pair that isn't the same SKU.
2. For each confirmed pair, exclude the Shopify item from Shopping ads. In Shopify, open **Google & YouTube > Products**, select the item, and choose *Exclude*. In Merchant Center, you can instead add a destination exclusion rule on the Shopify source.
3. Don't delete the PTG items. They carry the GTINs and labels.

## P013: Turn off the local destinations
Only do this if Pro-To-Grow has no physical retail store linked to a Google Business Profile.
1. Merchant Center > **Settings > Add-ons** (or **Marketing methods**).
2. Turn off **Local inventory ads** and **Free local listings**.
3. The 79 local disapprovals go away within about 24 hours, so the real issue count is easier to see.

## Not approved (still pending)
P001, P004 (infant/baby: waiting on legal), P005, P006, P008 to P010, P012, P014.
P003 and P011 were rejected as Shopify store changes. The brand and product_type they covered are now handled by the P007 feed.
