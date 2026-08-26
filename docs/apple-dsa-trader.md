# Apple DSA: if we switch to trader

**Current (2026-08-26):** Alien Lifestyles / team `WFT74BRMPV` completed DSA compliance and registered as a **non-trader**. That is enough for notarizing Developer ID apps (this launcher) and for non-commercial distribution.

This is not legal advice. If we later sell apps, in-app purchases, or otherwise act commercially toward EU consumers, we would re-declare as a **trader** in App Store Connect.

## When “trader” applies

Apple uses the EU Digital Services Act definition: acting for purposes related to trade, business, craft, or profession. Signals include:

- Paid apps, In-App Purchases, or ad-sponsored apps (especially at volume)
- Commercial practices toward consumers (ads, promoting products/services)
- VAT registration
- App developed in a professional/business capacity (vs hobby, no intent to commercialize)

Account Holder or Admin does this in App Store Connect: **Business → Agreements → Compliance → Digital Services Act**.

Official steps: [Manage EU DSA trader requirements](https://developer.apple.com/help/app-store-connect/manage-compliance-information/manage-european-union-digital-services-act-trader-requirements)

## What we would need to gather

**Contact (shown on EU App Store product pages):**

| If enrolled as | Provide |
| --- | --- |
| Organization | Phone + email (street address comes from the D-U-N-S record; change address via Apple, not this form) |
| Individual | Address or P.O. Box, phone, email |

Then:

1. **Verify email** with two-factor authentication.
2. **Verify phone** with two-factor authentication (or request manual verification if the number cannot receive codes).
3. **Upload documents** that currently show **business name and address** (business/legal records). If using a P.O. Box or other alternate address, also upload proof of association (e.g. a bill or receipt).
4. **Payment account details** in App Store Connect, if not already on file.
5. **Certify** that we only offer products/services that comply with applicable EU law.

Optional: a **Labels and Markings URL** for EU-required labels, per app.

Trader contact is **public** on EU storefronts, including phone. There is no “trader but hide the number” option.

## After trader is set

- We can still turn trader status **off or on per app** (App Information → App Store Regulations and Permits → Digital Services Act).
- First-time trader declaration requires the contact verification above.
- Incomplete/unverified trader status can **remove apps from EU storefronts**.

## Notarization vs App Store

Notarizing a local Mac app (Developer ID) is separate from App Store listing. DSA trader contact display is about **App Store pages in the EU**. We still needed the DSA *declaration* (including non-trader) so Apple’s agreements were current enough to accept notarization.
