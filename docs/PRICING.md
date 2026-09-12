# Pricing and entitlements

All OCR limits reset monthly. Yearly plans include two months free compared with paying monthly for twelve months.

| Plan | Monthly | Yearly | OCR pages/month | Batch limit | Bot Lab runs/month |
| --- | ---: | ---: | ---: | ---: | ---: |
| Free | ₦0 | — | 10 | 1 response | 0 |
| Student Pro | ₦3,500 | ₦35,000 | 30 | 30 responses | 1 |
| Researcher Pro | ₦5,000 | ₦50,000 | 35 | 100 responses | 2 |
| Organization | From ₦15,000 | From ₦150,000 | 100 pooled | 250 responses | 5 |

The Organization allowance is pooled across a maximum of 10 people. Organization onboarding and requests for additional Bot Lab runs are handled by an administrator.

Extra OCR costs ₦1,500 per 100 pages. Purchased pages apply to the current monthly usage period.

CSV is available on every plan. Student Pro and above include XLSX and the Google Forms Apps Script workflow. Advanced exports/analytics, organization self-service, and priority queue routing are represented as entitlements but must remain marked “coming soon” until their corresponding workflows are shipped.

Paystack is the only configured payment gateway. The backend chooses the amount, verifies successful status, amount, currency, and reference, and validates Paystack webhook signatures before granting an entitlement.
