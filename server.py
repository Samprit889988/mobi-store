#!/usr/bin/env python3
"""Mobi storefront: Python stdlib HTTP server with a SQLite catalog, accounts and demo orders."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, unquote
from http.cookies import SimpleCookie
import hashlib, hmac, json, mimetypes, secrets, sqlite3, time, uuid

ROOT = Path(__file__).resolve().parent
DB = ROOT / "store.db"
PORT = 8001
# 2026 additions are current-release demo listings. Prices are editable sample USD prices.
PRODUCTS = [
    ("iphone-18-pro", "iPhone 18 Pro", "Apple", "Flagship", 1099, 1099, "A20 Pro · 48MP variable-aperture camera · iOS 27", "#e8e4dc", "/static/products/phone-apple.jpg", 16, 4.9, "2026 launch"),
    ("iphone-18-pro-max", "iPhone 18 Pro Max", "Apple", "Flagship", 1199, 1199, "A20 Pro · Big-screen pro camera · Longer battery", "#e9e3df", "/static/products/phone-everyday.jpg", 12, 4.9, "2026 launch"),
    ("galaxy-s26-ultra", "Galaxy S26 Ultra", "Samsung", "Flagship", 1399, 1399, "Galaxy AI · Built-in privacy display · S Pen", "#e8e9e4", "/static/products/phone-samsung.jpg", 14, 4.8, "2026 launch"),
    ("pixel-11-pro", "Pixel 11 Pro", "Google", "Flagship", 999, 999, "Tensor G6 · Pro camera · Gemini built in", "#e9e5dc", "/static/products/phone-pixel.jpg", 11, 4.8, "2026 launch"),
    ("pixel-11-pro-fold", "Pixel 11 Pro Fold", "Google", "Foldable", 1799, 1799, "Big-screen foldable · Gemini · Pro camera", "#e6e4dd", "/static/products/phone-fold.jpg", 5, 4.6, "2026 launch"),
    ("iphone-16-pro", "iPhone 16 Pro", "Apple", "Flagship", 999, 1099, "A18 Pro chip · 48MP camera · Titanium", "#e8e4dc", "/static/products/phone-apple.jpg", 18, 4.9, "Best seller"),
    ("galaxy-s25-ultra", "Galaxy S25 Ultra", "Samsung", "Flagship", 899, 1299, "Galaxy AI · 200MP camera · S Pen", "#e8e9e4", "/static/products/phone-samsung.jpg", 12, 4.8, "Great deal"),
    ("pixel-9-pro", "Pixel 9 Pro", "Google", "Flagship", 799, 999, "Gemini built in · Pro camera · 7 years updates", "#e9e5dc", "/static/products/phone-pixel.jpg", 21, 4.8, "Staff pick"),
    ("iphone-16", "iPhone 16", "Apple", "Everyday", 699, 899, "A18 chip · Camera Control · All-day battery", "#e9e6e0", "/static/products/phone-everyday.jpg", 26, 4.7, "Save $200"),
    ("oneplus-13", "OnePlus 13", "OnePlus", "Flagship", 799, 899, "Hasselblad camera · 120Hz · 6000mAh", "#e5e8e2", "/static/products/phone-oneplus.jpg", 9, 4.6, "Fast ship"),
    ("galaxy-z-flip6", "Galaxy Z Flip6", "Samsung", "Foldable", 799, 1099, "Pocket-size foldable · FlexCam · Galaxy AI", "#e9e5e8", "/static/products/phone-fold.jpg", 7, 4.6, "Save $300"),
    ("pixel-9a", "Pixel 9a", "Google", "Everyday", 449, 499, "Brilliant photos · Gemini · 30+ hour battery", "#e9e7df", "/static/products/phone-pixel.jpg", 33, 4.7, "Great value"),
    ("nothing-phone-3a", "Phone (3a)", "Nothing", "Everyday", 379, 379, "Glyph interface · 50MP triple camera · 2-day power", "#e9e9e7", "/static/products/phone-oneplus.jpg", 15, 4.5, "Just in"),
    ("motorola-razr", "motorola razr+", "Motorola", "Foldable", 699, 799, "Iconic flip design · Edge-to-edge external display", "#e9e1df", "/static/products/phone-fold.jpg", 6, 4.4, "Save $100"),
    ("iphone-15", "iPhone 15", "Apple", "Everyday", 549, 699, "Dynamic Island · 48MP camera · USB-C", "#e9e3df", "/static/products/phone-everyday.jpg", 19, 4.6, "Under $600"),
    ("galaxy-a56", "Galaxy A56 5G", "Samsung", "Everyday", 449, 499, "Awesome screen · 50MP camera · 6 years of updates", "#e5e9e6", "/static/products/phone-samsung.jpg", 28, 4.4, "Everyday pick"),
    ("pixel-fold", "Pixel 9 Pro Fold", "Google", "Foldable", 1299, 1799, "Opens to a brilliant 8-inch display · Gemini", "#e6e4dd", "/static/products/phone-pixel.jpg", 4, 4.5, "Save $500"),
]
GALLERY_ASSETS = ["/static/products/phone-apple.jpg", "/static/products/phone-samsung.jpg", "/static/products/phone-pixel.jpg", "/static/products/phone-everyday.jpg", "/static/products/phone-oneplus.jpg", "/static/products/phone-fold.jpg"]

def connect():
    db = sqlite3.connect(DB, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db

def init_db():
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS products (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, brand TEXT NOT NULL, category TEXT NOT NULL,
          price INTEGER NOT NULL, compare_price INTEGER NOT NULL, description TEXT NOT NULL,
          swatch TEXT NOT NULL, image_url TEXT NOT NULL, stock INTEGER NOT NULL,
          rating REAL NOT NULL, badge TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS product_images (
          id INTEGER PRIMARY KEY AUTOINCREMENT, product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
          image_url TEXT NOT NULL, alt_text TEXT NOT NULL, sort_order INTEGER NOT NULL,
          UNIQUE(product_id, sort_order)
        );
        CREATE TABLE IF NOT EXISTS customers (
          id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT NOT NULL COLLATE NOCASE UNIQUE,
          phone TEXT NOT NULL, password_hash TEXT NOT NULL, password_salt TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS sessions (
          token_hash TEXT PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
          expires_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS orders (
          id TEXT PRIMARY KEY, customer_name TEXT NOT NULL, email TEXT NOT NULL,
          address TEXT NOT NULL, subtotal INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          customer_id INTEGER REFERENCES customers(id), payment_type TEXT NOT NULL DEFAULT 'demo', card_last4 TEXT NOT NULL DEFAULT '4242'
        );
        CREATE TABLE IF NOT EXISTS order_items (
          id INTEGER PRIMARY KEY AUTOINCREMENT, order_id TEXT NOT NULL REFERENCES orders(id),
          product_id TEXT NOT NULL REFERENCES products(id), quantity INTEGER NOT NULL,
          unit_price INTEGER NOT NULL
        );
        """)
        # Keep an existing prototype database usable after upgrades.
        cols = {r[1] for r in db.execute("PRAGMA table_info(orders)")}
        if "customer_id" not in cols: db.execute("ALTER TABLE orders ADD COLUMN customer_id INTEGER REFERENCES customers(id)")
        if "payment_type" not in cols: db.execute("ALTER TABLE orders ADD COLUMN payment_type TEXT NOT NULL DEFAULT 'demo'")
        if "card_last4" not in cols: db.execute("ALTER TABLE orders ADD COLUMN card_last4 TEXT NOT NULL DEFAULT '4242'")
        for row in PRODUCTS:
            db.execute("INSERT OR IGNORE INTO products VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", row)
        for ix, row in enumerate(PRODUCTS):
            pid, name, brand, *_ = row
            primary = row[8]
            # Product page gallery: locally hosted catalog images, no third-party image calls.
            others = [asset for asset in GALLERY_ASSETS if asset != primary]
            picks = [primary, others[ix % len(others)], others[(ix + 2) % len(others)]]
            for order, image in enumerate(picks):
                db.execute("INSERT OR IGNORE INTO product_images(product_id,image_url,alt_text,sort_order) VALUES(?,?,?,?)", (pid,image,f"{name} product view {order+1}",order))
        # Update the original demo products' listings while preserving live stock/order history.
        for row in PRODUCTS:
            db.execute("UPDATE products SET name=?,brand=?,category=?,price=?,compare_price=?,description=?,swatch=?,image_url=?,rating=?,badge=? WHERE id=?", (row[1],row[2],row[3],row[4],row[5],row[6],row[7],row[8],row[10],row[11],row[0]))
        db.execute("DELETE FROM sessions WHERE expires_at < ?", (int(time.time()),))

def public_customer(row):
    return {"id":row["id"],"name":row["name"],"email":row["email"],"phone":row["phone"],"created_at":row["created_at"]}
def pw_hash(password,salt):
    return hashlib.pbkdf2_hmac("sha256",password.encode(),salt,240000).hex()

def read_json(handler):
    length = int(handler.headers.get("Content-Length", "0"))
    if length > 128_000: raise ValueError("Request is too large.")
    return json.loads(handler.rfile.read(length) or b"{}")

class Handler(BaseHTTPRequestHandler):
    def send_json(self,data,status=200,headers=None):
        raw=json.dumps(data).encode(); self.send_response(status)
        self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(raw)))
        self.send_header("Cache-Control","no-store")
        for key,value in (headers or {}).items(): self.send_header(key,value)
        self.end_headers(); self.wfile.write(raw)
    def session_customer(self,db):
        cookie=SimpleCookie(self.headers.get("Cookie","")); morsel=cookie.get("mobi_session")
        if not morsel:return None
        token=morsel.value; digest=hashlib.sha256(token.encode()).hexdigest()
        row=db.execute("SELECT c.* FROM sessions s JOIN customers c ON c.id=s.customer_id WHERE s.token_hash=? AND s.expires_at>?",(digest,int(time.time()))).fetchone()
        return row
    def do_GET(self):
        path=unquote(urlparse(self.path).path)
        if path=="/api/products":
            with connect() as db: rows=db.execute("SELECT * FROM products ORDER BY CASE WHEN badge='2026 launch' THEN 0 WHEN badge='Best seller' THEN 1 ELSE 2 END, name").fetchall()
            return self.send_json([dict(row) for row in rows])
        if path.startswith("/api/products/"):
            pid=path.rsplit("/",1)[-1]
            with connect() as db:
                row=db.execute("SELECT * FROM products WHERE id=?",(pid,)).fetchone()
                if not row:return self.send_json({"error":"Product not found"},404)
                item=dict(row); item["images"]=[dict(r) for r in db.execute("SELECT image_url,alt_text,sort_order FROM product_images WHERE product_id=? ORDER BY sort_order",(pid,)).fetchall()]
            return self.send_json(item)
        if path=="/api/me":
            with connect() as db: customer=self.session_customer(db)
            return self.send_json({"user":public_customer(customer) if customer else None})
        if path=="/api/my-orders":
            with connect() as db:
                customer=self.session_customer(db)
                if not customer:return self.send_json({"error":"Sign in to see your orders."},401)
                orders=[]
                for order in db.execute("SELECT id,subtotal,created_at,payment_type,card_last4 FROM orders WHERE customer_id=? ORDER BY created_at DESC LIMIT 25",(customer["id"],)).fetchall():
                    o=dict(order); o["items"]=[dict(x) for x in db.execute("SELECT p.name,oi.quantity,oi.unit_price FROM order_items oi JOIN products p ON p.id=oi.product_id WHERE oi.order_id=?",(o["id"],)).fetchall()]; orders.append(o)
            return self.send_json({"orders":orders})
        if path=="/api/health":return self.send_json({"ok":True,"database":"sqlite","products":len(PRODUCTS)})
        target=ROOT/("index.html" if path=="/" else path.lstrip("/"))
        try:
            target=target.resolve()
            if ROOT not in target.parents and target!=ROOT:raise FileNotFoundError
            raw=target.read_bytes(); self.send_response(200)
            self.send_header("Content-Type",mimetypes.guess_type(str(target))[0] or "application/octet-stream")
            self.send_header("Content-Length",str(len(raw))); self.end_headers(); self.wfile.write(raw)
        except (FileNotFoundError,IsADirectoryError):self.send_error(404)
    def do_POST(self):
        path=urlparse(self.path).path
        try: data=read_json(self)
        except (ValueError,TypeError,json.JSONDecodeError):return self.send_json({"error":"Invalid request."},400)
        if path=="/api/signup":
            name=str(data.get("name","")).strip(); email=str(data.get("email","")).strip().lower(); phone=str(data.get("phone","")).strip(); password=str(data.get("password",""))
            if len(name)<2 or len(name)>120 or len(email)>250 or "@" not in email or len(phone)<7 or len(phone)>30 or not all(c.isdigit() or c in "+()- ." for c in phone) or len(password)<8 or len(password)>200:
                return self.send_json({"error":"Enter a valid name, email, phone number, and password (at least 8 characters)."},400)
            salt=secrets.token_bytes(16); token=secrets.token_urlsafe(32); exp=int(time.time())+60*60*24*14
            try:
                with connect() as db:
                    cur=db.execute("INSERT INTO customers(name,email,phone,password_hash,password_salt) VALUES(?,?,?,?,?)",(name,email,phone,pw_hash(password,salt),salt.hex()))
                    customer=db.execute("SELECT * FROM customers WHERE id=?",(cur.lastrowid,)).fetchone()
                    db.execute("INSERT INTO sessions(token_hash,customer_id,expires_at) VALUES(?,?,?)",(hashlib.sha256(token.encode()).hexdigest(),customer["id"],exp))
            except sqlite3.IntegrityError:return self.send_json({"error":"An account with that email already exists. Please sign in."},409)
            return self.send_json({"ok":True,"user":public_customer(customer)},201,{"Set-Cookie":f"mobi_session={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=1209600"})
        if path=="/api/login":
            email=str(data.get("email","")).strip().lower(); password=str(data.get("password",""))
            token=secrets.token_urlsafe(32); exp=int(time.time())+60*60*24*14
            with connect() as db:
                row=db.execute("SELECT * FROM customers WHERE email=? COLLATE NOCASE",(email,)).fetchone()
                ok=row and hmac.compare_digest(pw_hash(password,bytes.fromhex(row["password_salt"])),row["password_hash"])
                if not ok:return self.send_json({"error":"Email or password not recognized."},401)
                db.execute("INSERT INTO sessions(token_hash,customer_id,expires_at) VALUES(?,?,?)",(hashlib.sha256(token.encode()).hexdigest(),row["id"],exp))
            return self.send_json({"ok":True,"user":public_customer(row)},headers={"Set-Cookie":f"mobi_session={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=1209600"})
        if path=="/api/logout":
            cookie=SimpleCookie(self.headers.get("Cookie","")); m=cookie.get("mobi_session")
            if m:
                with connect() as db:db.execute("DELETE FROM sessions WHERE token_hash=?",(hashlib.sha256(m.value.encode()).hexdigest(),))
            return self.send_json({"ok":True},headers={"Set-Cookie":"mobi_session=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"})
        if path=="/api/orders":
            name=str(data.get("name","")).strip(); email=str(data.get("email","")).strip(); address=str(data.get("address","")).strip(); phone=str(data.get("phone","")).strip(); items=data.get("items",[])
            last4=str(data.get("card_last4",""))
            # Intentionally accept only a last-four display token. Full PAN/CVC never reaches or enters the database.
            if not (len(last4)==4 and last4.isdigit()):return self.send_json({"error":"Use the demo card form to complete this test checkout."},400)
            if not name or "@" not in email or not address or not items:return self.send_json({"error":"Please provide your contact details and at least one item."},400)
            if len(name)>120 or len(email)>250 or len(address)>500 or len(phone)>30 or len(items)>30:return self.send_json({"error":"Some checkout details are too long."},400)
            try:
                with connect() as db:
                    customer=self.session_customer(db); valid=[]; subtotal=0
                    for item in items:
                        pid=str(item.get("id","")); qty=item.get("quantity",0)
                        if not isinstance(qty,int) or qty<1 or qty>20:return self.send_json({"error":"Invalid quantity."},400)
                        product=db.execute("SELECT id,price,stock FROM products WHERE id=?",(pid,)).fetchone()
                        if not product or qty>product["stock"]:return self.send_json({"error":"A selected product is unavailable in that quantity."},400)
                        valid.append((product,qty)); subtotal+=product["price"]*qty
                    oid="MB-"+uuid.uuid4().hex[:8].upper()
                    db.execute("INSERT INTO orders(id,customer_name,email,address,subtotal,customer_id,payment_type,card_last4) VALUES(?,?,?,?,?,?,?,?)",(oid,name,email,address,subtotal,customer["id"] if customer else None,"DEMO ONLY",last4))
                    for product,qty in valid:
                        db.execute("INSERT INTO order_items(order_id,product_id,quantity,unit_price) VALUES(?,?,?,?)",(oid,product["id"],qty,product["price"]))
                        db.execute("UPDATE products SET stock=stock-? WHERE id=?",(qty,product["id"]))
                return self.send_json({"ok":True,"order_id":oid,"subtotal":subtotal,"payment":"DEMO ONLY — no charge"},201)
            except (ValueError,TypeError):return self.send_json({"error":"Invalid order data."},400)
        return self.send_json({"error":"Not found"},404)
    def log_message(self,fmt,*args):print("%s - %s"%(self.log_date_time_string(),fmt%args))

if __name__=="__main__":
    init_db(); print(f"Mobi store running at http://localhost:{PORT} · SQLite: {DB}")
    ThreadingHTTPServer(("0.0.0.0",PORT),Handler).serve_forever()
