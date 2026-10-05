# Mobi — smartphone storefront demo

A mobile-first, original smartphone shop with a separate catalog, product-detail pages and account page. It uses Python's standard library and SQLite, so no package install is needed.

## Run it

Requires Python 3.9+:

```bash
python3 server.py
```

Open **http://localhost:8001**. On first run, the server creates `store.db` and seeds 17 sample products and three gallery image records per product. The runtime database is intentionally excluded from version control so local account, session, and order data are not published.

## Features

- **Catalog:** 17 listings, including 2026 iPhone 18 Pro/Pro Max, Samsung Galaxy S26 Ultra, Pixel 11 Pro and Pixel 11 Pro Fold entries, plus earlier models; search, category filters, sort, ratings, stock and sample USD prices.
- **Product pages:** each item has a three-image gallery, details, stock count and add-to-bag button.
- **Accounts:** sign up with name, email, phone and password; sign in/out; view demo order history. Passwords use salted PBKDF2-HMAC-SHA256 hashes. Session cookies are HttpOnly and SameSite=Lax.
- **SQLite:** product catalog, gallery images, customers, sessions, orders and order line items.
- **Checkout:** test-only card UI prefilled with `4242 4242 4242 4242`, expiry `12/30`, CVC `123`. The browser checks the card locally and sends only its last four digits; the backend never receives or stores the full card number, expiry or CVC. No real payment is taken.
- **Local product imagery:** the six included JPEGs are served from `static/products/`; no external product image service is required. Product images, ratings, stock and prices are illustrative, not an official product feed.

## API

- `GET /api/products`
- `GET /api/products/<product-id>` (includes the gallery)
- `GET /api/health`
- `GET /api/me`, `GET /api/my-orders`
- `POST /api/signup`, `POST /api/login`, `POST /api/logout`
- `POST /api/orders` (demo orders only)

## Current-model references

- [Apple: iPhone 18 Pro and iPhone 18 Pro Max (Sep 9, 2026)](https://www.apple.com/newsroom/2026/09/apple-debuts-iphone-18-pro-and-iphone-18-pro-max/)
- [Samsung: Galaxy S26 Series](https://news.samsung.com/global/samsung-unveils-galaxy-s26-series-the-most-intuitive-galaxy-ai-phone-yet)
- [Google: Pixel 11 Pro Fold (Aug 12, 2026)](https://blog.google/products-and-platforms/devices/pixel/pixel-11-pro-fold/)

This is a functional prototype, not a production commerce system: no payment gateway, email/SMS verification, TLS setup, tax/shipping calculation, rate limiting, or administrative product editor is included. Configure TLS, stronger operational controls, real inventory/pricing feeds, and a PCI-compliant payment provider before using it with real customers.
