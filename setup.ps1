# setup.ps1 — EXN Shop complet (admin, panier, commandes, email prêt, style sombre rouge/noir)
# Ne lance PAS Python automatiquement — tu le lanceras manuellement.

# 1) Dossiers
New-Item -ItemType Directory -Force -Path "templates" | Out-Null
New-Item -ItemType Directory -Force -Path "static" | Out-Null
New-Item -ItemType Directory -Force -Path "static\uploads" | Out-Null

# 2) app.py
@"
import os, sqlite3, random, string
from uuid import uuid4
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = "exn_secret_key"
DB_NAME = "shop.db"
UPLOAD_FOLDER = os.path.join("static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ADMIN_USER = "getpost"
ADMIN_PASS = "tonght67"

# ---------- DB ----------
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS categories(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS produits(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL,
        prix REAL NOT NULL,
        description TEXT,
        image TEXT,
        categorie_id INTEGER,
        FOREIGN KEY(categorie_id) REFERENCES categories(id)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS commandes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL,
        items TEXT NOT NULL,
        total REAL NOT NULL,
        email TEXT
    )""")
    conn.commit()
    conn.close()

init_db()

# ---------- Contexte (menu) ----------
@app.context_processor
def inject_categories():
    try:
        conn = get_db()
        cats = conn.execute("SELECT id, nom FROM categories ORDER BY nom ASC").fetchall()
        conn.close()
    except Exception:
        cats = []
    return dict(nav_categories=cats)

# ---------- Pages publiques ----------
@app.route("/")
def index():
    conn = get_db()
    produits = conn.execute("SELECT * FROM produits ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("index.html", produits=produits)

@app.route("/categorie/<int:cat_id>")
def categorie(cat_id):
    conn = get_db()
    cat = conn.execute("SELECT * FROM categories WHERE id=?", (cat_id,)).fetchone()
    produits = conn.execute("SELECT * FROM produits WHERE categorie_id=? ORDER BY id DESC", (cat_id,)).fetchall()
    conn.close()
    return render_template("categorie.html", categorie=cat, produits=produits)

@app.route("/produit/<int:prod_id>")
def produit(prod_id):
    conn = get_db()
    p = conn.execute("SELECT * FROM produits WHERE id=?", (prod_id,)).fetchone()
    conn.close()
    if not p:
        return redirect(url_for("index"))
    return render_template("produit.html", produit=p)

# ---------- Panier ----------
@app.route("/ajouter_panier/<int:prod_id>", methods=["GET","POST"])
def ajouter_panier(prod_id):
    session.setdefault("panier", [])
    session["panier"].append(prod_id)
    session.modified = True
    return redirect(url_for("panier"))

@app.route("/supprimer_panier/<int:prod_id>")
def supprimer_panier(prod_id):
    session.setdefault("panier", [])
    session["panier"] = [pid for pid in session["panier"] if pid != prod_id]
    session.modified = True
    return redirect(url_for("panier"))

@app.route("/vider_panier")
def vider_panier():
    session["panier"] = []
    session.modified = True
    return redirect(url_for("panier"))

@app.route("/panier")
def panier():
    panier_ids = session.get("panier", [])
    conn = get_db()
    produits, total = [], 0.0
    for pid in panier_ids:
        p = conn.execute("SELECT * FROM produits WHERE id=?", (pid,)).fetchone()
        if p:
            produits.append(p)
            total += float(p["prix"])
    conn.close()
    return render_template("panier.html", produits=produits, total=total)

@app.route("/valider_commande", methods=["POST"])
def valider_commande():
    panier_ids = session.get("panier", [])
    if not panier_ids:
        return redirect(url_for("panier"))
    email = request.form.get("email","")
    conn = get_db()
    items, total = [], 0.0
    for pid in panier_ids:
        p = conn.execute("SELECT * FROM produits WHERE id=?", (pid,)).fetchone()
        if p:
            items.append(f"{p['nom']} ({p['prix']})")
            total += float(p["prix"])
    code = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
    conn.execute("INSERT INTO commandes (code, items, total, email) VALUES (?, ?, ?, ?)", (code, ", ".join(items), total, email))
    conn.commit()
    conn.close()
    session["panier"] = []
    return render_template("commande.html", code=code, items=items, total=total)

# ---------- Connexion / Admin ----------
@app.route("/connexion", methods=["GET","POST"])
def connexion():
    if request.method == "POST":
        user = request.form.get("username","")
        pwd  = request.form.get("password","")
        if user == ADMIN_USER and pwd == ADMIN_PASS:
            session["admin"] = True
            return redirect(url_for("admin"))
        return render_template("connexion.html", error="Identifiants incorrects")
    return render_template("connexion.html")

@app.route("/deconnexion")
def deconnexion():
    session.pop("admin", None)
    return redirect(url_for("index"))

def require_admin():
    return bool(session.get("admin"))

@app.route("/admin")
def admin():
    if not require_admin():
        return redirect(url_for("connexion"))
    conn = get_db()
    categories = conn.execute("SELECT * FROM categories ORDER BY nom ASC").fetchall()
    produits   = conn.execute("SELECT * FROM produits ORDER BY id DESC").fetchall()
    commandes  = conn.execute("SELECT * FROM commandes ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("admin.html", categories=categories, produits=produits, commandes=commandes)

# ---- Catégories
@app.route("/admin/ajouter_categorie", methods=["POST"])
def ajouter_categorie():
    if not require_admin(): return redirect(url_for("connexion"))
    nom = request.form.get("nom","").strip()
    if nom:
        conn = get_db()
        conn.execute("INSERT INTO categories (nom) VALUES (?)", (nom,))
        conn.commit(); conn.close()
    return redirect(url_for("admin"))

@app.route("/admin/supprimer_categorie/<int:cat_id>")
def supprimer_categorie(cat_id):
    if not require_admin(): return redirect(url_for("connexion"))
    conn = get_db()
    conn.execute("UPDATE produits SET categorie_id=NULL WHERE categorie_id=?", (cat_id,))
    conn.execute("DELETE FROM categories WHERE id=?", (cat_id,))
    conn.commit(); conn.close()
    return redirect(url_for("admin"))

# ---- Produits
def _save_image(file_storage):
    if not file_storage or not file_storage.filename:
        return None
    safe = os.path.basename(file_storage.filename)
    ext = os.path.splitext(safe)[1]  # garde l extension d origine (jpg/png/webp/gif, etc.)
    unique = uuid4().hex + ext
    path = os.path.join(UPLOAD_FOLDER, unique)
    file_storage.save(path)
    return f"uploads/{unique}"

@app.route("/admin/ajouter_produit", methods=["POST"])
def admin_ajouter_produit():
    if not require_admin(): return redirect(url_for("connexion"))
    nom = request.form.get("nom","").strip()
    prix = float(request.form.get("prix","0") or 0)
    description = request.form.get("description","").strip()
    categorie_id = request.form.get("categorie_id") or None
    image = _save_image(request.files.get("image"))
    conn = get_db()
    conn.execute("""INSERT INTO produits (nom, prix, description, image, categorie_id)
                    VALUES (?, ?, ?, ?, ?)""", (nom, prix, description, image, categorie_id))
    conn.commit(); conn.close()
    return redirect(url_for("admin"))

@app.route("/admin/modifier_produit/<int:prod_id>", methods=["GET","POST"])
def admin_modifier_produit(prod_id):
    if not require_admin(): return redirect(url_for("connexion"))
    conn = get_db()
    if request.method == "POST":
        nom = request.form.get("nom","").strip()
        prix = float(request.form.get("prix","0") or 0)
        description = request.form.get("description","").strip()
        categorie_id = request.form.get("categorie_id") or None
        image_exist = request.form.get("image_exist") or None
        image_new = _save_image(request.files.get("image"))
        image = image_new if image_new else image_exist
        conn.execute("""UPDATE produits SET nom=?, prix=?, description=?, image=?, categorie_id=? WHERE id=?""",
                     (nom, prix, description, image, categorie_id, prod_id))
        conn.commit(); conn.close()
        return redirect(url_for("admin"))
    p = conn.execute("SELECT * FROM produits WHERE id=?", (prod_id,)).fetchone()
    categories = conn.execute("SELECT * FROM categories ORDER BY nom ASC").fetchall()
    conn.close()
    return render_template("modifier_produit.html", produit=p, categories=categories)

@app.route("/admin/supprimer_produit/<int:prod_id>")
def admin_supprimer_produit(prod_id):
    if not require_admin(): return redirect(url_for("connexion"))
    conn = get_db()
    conn.execute("DELETE FROM produits WHERE id=?", (prod_id,))
    conn.commit(); conn.close()
    return redirect(url_for("admin"))

# ---- Commandes
@app.route("/admin/rechercher_commande", methods=["POST"])
def rechercher_commande():
    if not require_admin(): return redirect(url_for("connexion"))
    code = (request.form.get("code","") or "").upper()
    conn = get_db()
    cmd = conn.execute("SELECT * FROM commandes WHERE code=?", (code,)).fetchone()
    conn.close()
    if cmd:
        return render_template("commande.html", code=cmd["code"], items=cmd["items"].split(", "), total=cmd["total"])
    return render_template("commande.html", code=None, items=[], total=0)

if __name__ == "__main__":
    app.run(debug=True)
"@ | Set-Content -Encoding UTF8 "app.py"

# 3) templates/base.html
@"
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <title>EXN Shop</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
  <canvas id="bg"></canvas>
  <header class="topbar">
    <div class="brand">EXN <span>SHOP</span></div>
    <nav>
      <a href="{{ url_for('index') }}">Accueil</a>
      {% for c in nav_categories %}
        <a href="{{ url_for('categorie', cat_id=c['id']) }}">{{ c['nom'] }}</a>
      {% endfor %}
      <a href="{{ url_for('panier') }}">Panier</a>
      {% if session.get('admin') %}
        <a href="{{ url_for('admin') }}">Admin</a>
        <a href="{{ url_for('deconnexion') }}">Deconnexion</a>
      {% else %}
        <a href="{{ url_for('connexion') }}">Connexion</a>
      {% endif %}
    </nav>
  </header>
  <main class="container">
    {% block content %}{% endblock %}
  </main>
  <script src="{{ url_for('static', filename='stars.js') }}"></script>
</body>
</html>
"@ | Set-Content -Encoding UTF8 "templates\base.html"

# 4) templates/index.html
@"
{% extends 'base.html' %}
{% block content %}
<h1 class="title">Tous les produits</h1>
<div class="grid">
  {% for p in produits %}
  <article class="card">
    <div class="thumb">
      {% if p['image'] %}
        <img src="{{ url_for('static', filename=p['image']) }}" alt="{{ p['nom'] }}">
      {% else %}
        <img src="{{ url_for('static', filename='placeholder.svg') }}" alt="{{ p['nom'] }}">
      {% endif %}
    </div>
    <h3 class="name">{{ p['nom'] }}</h3>
    <div class="meta">
      <span class="price">{{ '{:.2f}'.format(p['prix']) }}</span>
      <a class="btn" href="{{ url_for('produit', prod_id=p['id']) }}">Voir</a>
    </div>
  </article>
  {% else %}
  <p>Aucun produit pour le moment.</p>
  {% endfor %}
</div>
{% endblock %}
"@ | Set-Content -Encoding UTF8 "templates\index.html"

# 5) templates/categorie.html
@"
{% extends 'base.html' %}
{% block content %}
<h1 class="title">Categorie : {{ categorie['nom'] if categorie else 'Inconnue' }}</h1>
<div class="grid">
  {% for p in produits %}
  <article class="card">
    <div class="thumb">
      {% if p['image'] %}
        <img src="{{ url_for('static', filename=p['image']) }}" alt="{{ p['nom'] }}">
      {% else %}
        <img src="{{ url_for('static', filename='placeholder.svg') }}" alt="{{ p['nom'] }}">
      {% endif %}
    </div>
    <h3 class="name">{{ p['nom'] }}</h3>
    <div class="meta">
      <span class="price">{{ '{:.2f}'.format(p['prix']) }}</span>
      <a class="btn" href="{{ url_for('produit', prod_id=p['id']) }}">Voir</a>
    </div>
  </article>
  {% else %}
  <p>Aucun produit dans cette categorie.</p>
  {% endfor %}
</div>
{% endblock %}
"@ | Set-Content -Encoding UTF8 "templates\categorie.html"

# 6) templates/produit.html
@"
{% extends 'base.html' %}
{% block content %}
<section class="product-detail glass">
  <div class="left">
    {% if produit['image'] %}
      <img src="{{ url_for('static', filename=produit['image']) }}" alt="{{ produit['nom'] }}">
    {% else %}
      <img src="{{ url_for('static', filename='placeholder.svg') }}" alt="{{ produit['nom'] }}">
    {% endif %}
  </div>
  <div class="right">
    <h1>{{ produit['nom'] }}</h1>
    <p class="desc">{{ produit['description'] or '' }}</p>
    <div class="buy">
      <span class="price">{{ '{:.2f}'.format(produit['prix']) }}</span>
      <form method="POST" action="{{ url_for('ajouter_panier', prod_id=produit['id']) }}">
        <button class="btn">Ajouter au panier</button>
      </form>
    </div>
  </div>
</section>
{% endblock %}
"@ | Set-Content -Encoding UTF8 "templates\produit.html"

# 7) templates/panier.html
@"
{% extends 'base.html' %}
{% block content %}
<h1 class="title">Votre panier</h1>
{% if produits %}
<div class="cart">
  {% for p in produits %}
  <div class="cart-item glass">
    <div class="ci-left">
      {% if p['image'] %}
        <img src="{{ url_for('static', filename=p['image']) }}" alt="{{ p['nom'] }}">
      {% else %}
        <img src="{{ url_for('static', filename='placeholder.svg') }}" alt="{{ p['nom'] }}">
      {% endif %}
      <div>
        <div class="ci-name">{{ p['nom'] }}</div>
        <div class="ci-price">{{ '{:.2f}'.format(p['prix']) }}</div>
      </div>
    </div>
    <a class="link danger" href="{{ url_for('supprimer_panier', prod_id=p['id']) }}">Supprimer</a>
  </div>
  {% endfor %}
</div>
<div class="cart-total glass">
  <div>Total : <strong>{{ '{:.2f}'.format(total) }}</strong></div>
  <form method="POST" action="{{ url_for('valider_commande') }}">
    <input type="email" name="email" placeholder="Votre email" required>
    <button class="btn">Valider la commande</button>
  </form>
  <a class="link" href="{{ url_for('vider_panier') }}">Vider le panier</a>
</div>
{% else %}
<p>Votre panier est vide.</p>
{% endif %}
{% endblock %}
"@ | Set-Content -Encoding UTF8 "templates\panier.html"

# 8) templates/commande.html
@"
{% extends 'base.html' %}
{% block content %}
<section class="order glass">
  {% if code %}
    <h1>Commande validee</h1>
    <p>Votre numero de commande :</p>
    <div class="order-code">{{ code }}</div>
    <p>Articles : {{ items|join(', ') }}</p>
    <p>Total : <strong>{{ '{:.2f}'.format(total) }}</strong></p>
  {% else %}
    <h1>Commande introuvable</h1>
    <p>Verifiez le code et reessayez.</p>
  {% endif %}
</section>
{% endblock %}
"@ | Set-Content -Encoding UTF8 "templates\commande.html"

# 9) templates/connexion.html
@"
{% extends 'base.html' %}
{% block content %}
<section class="login glass">
  <h1>Connexion</h1>
  <form method="POST" class="form">
    <input type="text" name="username" placeholder="Identifiant" required>
    <input type="password" name="password" placeholder="Mot de passe" required>
    <button class="btn" type="submit">Se connecter</button>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
  </form>
</section>
{% endblock %}
"@ | Set-Content -Encoding UTF8 "templates\connexion.html"

# 10) templates/admin.html
@"
{% extends 'base.html' %}
{% block content %}
<section class="admin">
  <h1 class="title">Panneau Admin</h1>

  <div class="admin-grid">
    <div class="card glass">
      <h2>Categories</h2>
      <ul class="list">
        {% for c in categories %}
          <li>{{ c['nom'] }}
            <a class="link danger" href="{{ url_for('supprimer_categorie', cat_id=c['id']) }}">Supprimer</a>
          </li>
        {% else %}
          <li>Aucune categorie</li>
        {% endfor %}
      </ul>
      <form class="form" method="POST" action="{{ url_for('ajouter_categorie') }}">
        <input type="text" name="nom" placeholder="Nouvelle categorie" required>
        <button class="btn" type="submit">Ajouter</button>
      </form>
    </div>

    <div class="card glass">
      <h2>Produits</h2>
      <ul class="list">
        {% for p in produits %}
          <li>{{ p['nom'] }} — {{ '{:.2f}'.format(p['prix']) }}
            <a class="link" href="{{ url_for('admin_modifier_produit', prod_id=p['id']) }}">Modifier</a>
            <a class="link danger" href="{{ url_for('admin_supprimer_produit', prod_id=p['id']) }}">Supprimer</a>
          </li>
        {% else %}
          <li>Aucun produit</li>
        {% endfor %}
      </ul>

      <h3>Ajouter un produit</h3>
      <form class="form" method="POST" action="{{ url_for('admin_ajouter_produit') }}" enctype="multipart/form-data">
        <input type="text" name="nom" placeholder="Nom" required>
        <input type="number" step="0.01" name="prix" placeholder="Prix" required>
        <textarea name="description" placeholder="Description"></textarea>
        <label>Image (depuis votre PC) :</label>
        <input type="file" name="image" accept="image/*">
        <label>Categorie :</label>
        <select name="categorie_id">
          {% for c in categories %}
            <option value="{{ c['id'] }}">{{ c['nom'] }}</option>
          {% endfor %}
        </select>
        <button class="btn" type="submit">Ajouter</button>
      </form>
    </div>
  </div>

  <div class="card glass">
    <h2>Rechercher une commande</h2>
    <form class="form" method="POST" action="{{ url_for('rechercher_commande') }}">
      <input type="text" name="code" placeholder="Code commande" required>
      <button class="btn" type="submit">Rechercher</button>
    </form>
  </div>
</section>
{% endblock %}
"@ | Set-Content -Encoding UTF8 "templates\admin.html"

# 11) templates/modifier_produit.html
@"
{% extends 'base.html' %}
{% block content %}
<section class="admin">
  <h1 class="title">Modifier produit</h1>
  <form class="form glass" method="POST" enctype="multipart/form-data">
    <input type="text" name="nom" value="{{ produit['nom'] }}" required>
    <input type="number" step="0.01" name="prix" value="{{ produit['prix'] }}" required>
    <textarea name="description" placeholder="Description">{{ produit['description'] or '' }}</textarea>

    <label>Image actuelle :</label>
    {% if produit['image'] %}
      <img class="mini" src="{{ url_for('static', filename=produit['image']) }}" alt="{{ produit['nom'] }}">
    {% else %}
      <img class="mini" src="{{ url_for('static', filename='placeholder.svg') }}" alt="{{ produit['nom'] }}">
    {% endif %}
    <input type="hidden" name="image_exist" value="{{ produit['image'] or '' }}">

    <label>Nouvelle image (optionnel) :</label>
    <input type="file" name="image" accept="image/*">

    <label>Categorie :</label>
    <select name="categorie_id">
      {% for c in categories %}
        <option value="{{ c['id'] }}" {% if produit['categorie_id'] == c['id'] %}selected{% endif %}>{{ c['nom'] }}</option>
      {% endfor %}
    </select>

    <button class="btn" type="submit">Enregistrer</button>
  </form>
</section>
{% endblock %}
"@ | Set-Content -Encoding UTF8 "templates\modifier_produit.html"

# 12) static/style.css (sombre rouge/noir + neons + constellations)
@"
:root{
  --bg:#0b0b0d;
  --panel:rgba(22,22,26,.7);
  --glass:rgba(26,26,32,.6);
  --red:#ff1e42;
  --text:#e9e9ef;
  --muted:#a5a6ad;
  --glow:0 0 18px rgba(255,30,66,.55);
}
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:var(--bg);color:var(--text);font-family:Montserrat,system-ui,Segoe UI,Roboto,Arial,sans-serif}
#bg{position:fixed;inset:0;z-index:-1}

.topbar{
  position:sticky;top:0;z-index:10;
  background:linear-gradient(180deg, rgba(15,15,18,.9), rgba(15,15,18,.65));
  backdrop-filter: blur(8px);
  border-bottom:1px solid rgba(255,255,255,.06);
  display:flex;align-items:center;justify-content:space-between;
  padding:14px 22px
}
.brand{font-weight:800;letter-spacing:.5px}
.brand span{color:var(--red);text-shadow:var(--glow)}
.topbar nav a{margin-left:14px;text-decoration:none;color:var(--muted);font-weight:600}
.topbar nav a:hover{color:#fff;text-shadow:var(--glow)}

.container{max-width:1180px;margin:32px auto;padding:0 16px}
.title{text-align:center;margin:6px 0 24px 0;font-size:28px;font-weight:800;text-shadow:var(--glow)}

.grid{display:grid;gap:22px;grid-template-columns: repeat(auto-fill, minmax(220px, 1fr))}
.card{
  background:var(--glass);border:1px solid rgba(255,255,255,.06);border-radius:16px;
  overflow:hidden;backdrop-filter: blur(10px);
  box-shadow:0 6px 28px rgba(0,0,0,.35);transition:.25s transform,.25s box-shadow
}
.card:hover{transform:translateY(-4px);box-shadow:0 10px 36px rgba(0,0,0,.5)}
.thumb{aspect-ratio:1/1;overflow:hidden}
.thumb img{width:100%;height:100%;object-fit:cover;display:block}
.name{padding:12px 14px 0 14px;font-weight:700;font-size:16px}
.meta{display:flex;align-items:center;justify-content:space-between;padding:12px 14px 16px 14px}
.price{font-weight:800}
.btn{appearance:none;border:0;background:var(--red);color:white;padding:8px 12px;border-radius:10px;cursor:pointer;box-shadow:var(--glow);text-decoration:none;font-weight:700}
.btn:hover{filter:brightness(1.05)}

.glass{background:var(--glass);border:1px solid rgba(255,255,255,.06);border-radius:16px;backdrop-filter: blur(10px);padding:18px}

.product-detail{display:grid;gap:24px;grid-template-columns:1fr 1fr}
.product-detail .left img{width:100%;border-radius:14px;border:1px solid rgba(255,255,255,.06)}
.product-detail .right h1{margin:0 0 10px 0}
.product-detail .desc{color:var(--muted);line-height:1.6}
.product-detail .buy{display:flex;gap:14px;align-items:center;margin-top:14px}

.cart{display:flex;flex-direction:column;gap:12px}
.cart-item{display:flex;align-items:center;justify-content:space-between}
.ci-left{display:flex;gap:12px;align-items:center}
.ci-left img{width:64px;height:64px;object-fit:cover;border-radius:10px;border:1px solid rgba(255,255,255,.06)}
.link{color:#fff;text-decoration:none;font-weight:700}
.link.danger{color:#ff7a7a}
.cart-total{margin-top:16px;display:flex;gap:12px;align-items:center}

.order{text-align:center}
.order-code{font-size:28px;font-weight:800;letter-spacing:2px;color:#fff;text-shadow:var(--glow);margin:8px 0 14px}

.login .form, .admin .form{display:flex;flex-direction:column;gap:10px}
.form input, .form textarea, .form select{
  background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.08);color:#fff;padding:10px;border-radius:10px;outline:none
}
.form textarea{min-height:92px;resize:vertical}
.error{color:#ff8080;margin-top:6px}

.admin .admin-grid{display:grid;gap:18px;grid-template-columns:1fr 1fr}
.list{list-style:none;margin:0;padding:0}
.list li{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px dashed rgba(255,255,255,.08)}
.mini{width:120px;height:120px;object-fit:cover;border-radius:10px;border:1px solid rgba(255,255,255,.06);margin:8px 0}

@media (max-width: 880px){
  .product-detail{grid-template-columns:1fr}
  .admin .admin-grid{grid-template-columns:1fr}
}
"@ | Set-Content -Encoding UTF8 "static\style.css"

# 13) static/stars.js (constellations rouge)
@"
const canvas = document.getElementById('bg');
if(canvas){
  const ctx = canvas.getContext('2d');
  const DPR = window.devicePixelRatio || 1;
  function resize(){
    canvas.width = innerWidth * DPR;
    canvas.height = innerHeight * DPR;
    ctx.setTransform(DPR,0,0,DPR,0,0);
  }
  resize(); addEventListener('resize', resize);

  const stars = Array.from({length: 120}).map(() => ({
    x: Math.random()*innerWidth,
    y: Math.random()*innerHeight,
    vx: (Math.random()-.5)*0.25,
    vy: (Math.random()-.5)*0.25,
    r: Math.random()*1.4+0.4
  }));

  function tick(){
    ctx.clearRect(0,0,innerWidth,innerHeight);
    ctx.fillStyle = 'rgba(255,255,255,0.9)';
    for(const s of stars){
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.r, 0, Math.PI*2);
      ctx.fill();
      s.x += s.vx; s.y += s.vy;
      if(s.x<0||s.x>innerWidth) s.vx*=-1;
      if(s.y<0||s.y>innerHeight) s.vy*=-1;
    }
    ctx.strokeStyle = 'rgba(255,30,66,0.20)';
    ctx.lineWidth = 1;
    for(let i=0;i<stars.length;i++){
      for(let j=i+1;j<stars.length;j++){
        const a = stars[i], b = stars[j];
        const dx = a.x-b.x, dy = a.y-b.y;
        const d2 = dx*dx + dy*dy;
        if(d2 < 160*160){
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }
      }
    }
    requestAnimationFrame(tick);
  }
  tick();
}
"@ | Set-Content -Encoding UTF8 "static\stars.js"

# 14) static/placeholder.svg
@"
<svg xmlns='http://www.w3.org/2000/svg' width='600' height='600'>
  <defs>
    <linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>
      <stop offset='0%' stop-color='#1a1a22'/>
      <stop offset='100%' stop-color='#0b0b0d'/>
    </linearGradient>
  </defs>
  <rect width='100%' height='100%' fill='url(#g)'/>
  <circle cx='300' cy='300' r='180' fill='none' stroke='#ff1e42' stroke-width='6' opacity='.6'/>
  <text x='50%' y='52%' text-anchor='middle' font-size='28' font-family='Montserrat' fill='#e9e9ef'>Image</text>
</svg>
"@ | Set-Content -Encoding UTF8 "static\placeholder.svg"

# 15) DB vide (fichier, SQLite creera les tables au 1er run si besoin)
if (-Not (Test-Path "shop.db")) { New-Item -ItemType File -Path "shop.db" | Out-Null }

Write-Host "✅ Setup termine. Etapes :" -ForegroundColor Green
Write-Host "1) pip install flask" -ForegroundColor Yellow
Write-Host "2) python app.py  -> http://127.0.0.1:5000" -ForegroundColor Yellow
Write-Host "Admin: getpost / tonght67" -ForegroundColor Yellow
