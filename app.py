from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
import os, random, string

app = Flask(__name__)
app.secret_key = "supersecret"

# --- Config BDD ---
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///shop.db"
db = SQLAlchemy(app)

# --- Modèles ---
class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    prix = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=True)
    image = db.Column(db.String(200), nullable=True)

class Commande(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), nullable=False)
    contenu = db.Column(db.Text, nullable=False)
    total = db.Column(db.Float, nullable=False)

class Theme(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    primary = db.Column(db.String(20), default="#e0112b")
    secondary = db.Column(db.String(20), default="#111")

# --- Création BDD ---
if not os.path.exists("shop.db"):
    with app.app_context():
        db.create_all()
        db.session.add(Theme(primary="#e0112b", secondary="#111"))
        db.session.commit()

# --- Admin ---
ADMIN_USER = "getpost"
ADMIN_PASS = "tonght67"

# --- Fonctions utilitaires ---
def generer_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def get_theme():
    theme = Theme.query.first()
    return {"primary": theme.primary, "secondary": theme.secondary} if theme else {"primary": "#e0112b", "secondary": "#111"}

# --- Routes ---
@app.route("/")
def shop():
    articles = Article.query.all()
    return render_template("shop.html", articles=articles, couleurs=get_theme())

@app.route("/produit/<int:id>")
def produit(id):
    article = Article.query.get_or_404(id)
    return render_template("produit.html", article=article, couleurs=get_theme())

@app.route("/ajouter_panier/<int:id>")
def ajouter_panier(id):
    panier = session.get("panier", [])
    panier.append(id)
    session["panier"] = panier
    return redirect(url_for("panier"))

@app.route("/panier", methods=["GET", "POST"])
def panier():
    panier = session.get("panier", [])
    items, total = [], 0
    for art_id in panier:
        article = Article.query.get(art_id)
        if article:
            items.append(article)
            total += article.prix

    if request.method == "POST" and items:
        code = generer_code()
        contenu = ", ".join([a.nom for a in items])
        db.session.add(Commande(code=code, contenu=contenu, total=total))
        db.session.commit()
        session.pop("panier", None)
        return render_template("confirmation.html", code=code, total=total, couleurs=get_theme())

    return render_template("panier.html", items=items, total=total, couleurs=get_theme())

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form["username"] == ADMIN_USER and request.form["password"] == ADMIN_PASS:
            session["admin"] = True
            return redirect(url_for("admin"))
    return render_template("login.html", couleurs=get_theme())

@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("shop"))

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if not session.get("admin"):
        return redirect(url_for("login"))

    if request.method == "POST":
        if "ajouter" in request.form:
            nom = request.form["nom"]
            prix = float(request.form["prix"])
            desc = request.form.get("description")
            image = request.form.get("image")
            db.session.add(Article(nom=nom, prix=prix, description=desc, image=image))
            db.session.commit()
        elif "supprimer" in request.form:
            id_article = int(request.form["supprimer"])
            Article.query.filter_by(id=id_article).delete()
            db.session.commit()
        elif "changer_couleurs" in request.form:
            theme = Theme.query.first()
            theme.primary = request.form["primary"]
            theme.secondary = request.form["secondary"]
            db.session.commit()

    return render_template("admin.html", articles=Article.query.all(), commandes=Commande.query.all(), couleurs=get_theme())

@app.route("/commande", methods=["POST"])
def commande():
    code = request.form["code"]
    commande = Commande.query.filter_by(code=code).first()
    return render_template("commande_resultat.html", commande=commande, couleurs=get_theme())

if __name__ == "__main__":
    app.run(debug=True)


