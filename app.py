#!/usr/bin/env python3
"""Visiolux : visuels rétro-terminal sur CRT composite + page web de contrôle.

Variables d'environnement (facultatives) :
  VISIOLUX_PORT   port web (80 par défaut)
  VISIOLUX_DATA   dossier des réglages et de l'image (/var/lib/visiolux)
  VISIOLUX_APERCU dossier : mode test sans écran, écrit apercu.png chaque seconde
"""
import json
import os
import random
import subprocess
import threading
import time
import traceback

import numpy as np
from flask import Flask, jsonify, request, send_file
from PIL import Image, ImageDraw

import scenes as S
from moteur import COULEURS, H, MX, W, Apercu, Framebuffer, attenuer, police

ICI = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("VISIOLUX_DATA", "/var/lib/visiolux")
PORT = int(os.environ.get("VISIOLUX_PORT", "80"))
APERCU = os.environ.get("VISIOLUX_APERCU")
os.makedirs(DATA, exist_ok=True)
FICHIER_ETAT = os.path.join(DATA, "etat.json")
FICHIER_IMAGE = os.path.join(DATA, "image.png")
FPS = 15


class Etat:
    DEFAUT = {"scene": "demarrage", "couleur": "vert", "auto": True, "duree": 60, "message": ""}

    def __init__(self):
        self.lock = threading.Lock()
        self.d = dict(self.DEFAUT)
        try:
            with open(FICHIER_ETAT) as f:
                self.d.update({k: v for k, v in json.load(f).items() if k in self.DEFAUT})
        except (OSError, ValueError):
            pass
        if self.d["scene"].startswith("_"):
            self.d["scene"] = "demarrage"
        self.version = 0

    def lire(self):
        with self.lock:
            return dict(self.d, version=self.version)

    def maj(self, sauver=True, **kw):
        with self.lock:
            self.d.update(kw)
            self.version += 1
            if sauver:
                tmp = FICHIER_ETAT + ".tmp"
                with open(tmp, "w") as f:
                    json.dump(self.d, f)
                os.replace(tmp, FICHIER_ETAT)


class Afficheur(threading.Thread):
    def __init__(self, etat, sortie):
        super().__init__(daemon=True)
        self.etat, self.sortie = etat, sortie
        self.scenes = S.creer_scenes(FICHIER_IMAGE)
        self.nom = None

    def _lancer(self, nom, e):
        self.nom = nom
        self.scenes[nom][1].demarrer(e)
        self.transition = 0.35
        self.debut = time.monotonic()

    def run(self):
        img = Image.new("RGB", (W, H))
        d = ImageDraw.Draw(img)
        version, prec, msg = -1, time.monotonic(), None
        self.transition = 0
        while True:
            t = time.monotonic()
            dt, prec = min(0.2, t - prec), t
            e = self.etat.lire()
            if e["version"] != version:
                version = e["version"]
                if e["scene"] != self.nom or (e["scene"] == "message" and e.get("msg_n") != msg):
                    self._lancer(e["scene"] if e["scene"] in self.scenes else "demarrage", e)
                msg = e.get("msg_n")
            elif e["auto"] and self.nom in S.ROTATION and t - self.debut > e["duree"]:
                self._lancer(S.ROTATION[(S.ROTATION.index(self.nom) + 1) % len(S.ROTATION)], e)

            base = COULEURS.get(e["couleur"], COULEURS["vert"])
            couleur = attenuer(base, random.uniform(0.95, 1.0))   # léger scintillement
            d.rectangle([0, 0, W, H], fill=(0, 0, 0))
            if self.transition > 0:
                self.transition -= dt
                bruit = (np.random.rand(H // 8, W // 8, 1) > 0.65) * np.array(couleur, dtype=np.uint8)
                img.paste(Image.fromarray(bruit.astype(np.uint8)).resize((W, H), Image.NEAREST))
            else:
                try:
                    self.scenes[self.nom][1].dessiner(img, d, t, dt, couleur)
                except Exception:
                    traceback.print_exc()
                    d.text((MX, H // 2), "ERREUR DANS LA SCENE", font=police(24), fill=couleur)
                    time.sleep(1)
            self.sortie.afficher(img)
            time.sleep(max(0.0, 1 / FPS - (time.monotonic() - t)))


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024
etat = Etat()
afficheur = None


def erreur(msg, code=400):
    return jsonify({"ok": False, "erreur": msg}), code


@app.get("/")
def page():
    return send_file(os.path.join(ICI, "page.html"))


@app.get("/api/etat")
def api_etat():
    e = etat.lire()
    e["affiche"] = afficheur.nom
    e["scenes"] = [[k, v[0]] for k, v in afficheur.scenes.items() if not k.startswith("_")]
    e["couleurs"] = list(COULEURS)
    e["image"] = os.path.exists(FICHIER_IMAGE)
    return jsonify(e)


@app.post("/api/scene")
def api_scene():
    nom = (request.get_json(silent=True) or {}).get("scene", "")
    if nom not in afficheur.scenes or nom.startswith("_"):
        return erreur("scène inconnue")
    etat.maj(scene=nom)
    return jsonify({"ok": True})


@app.post("/api/reglages")
def api_reglages():
    j = request.get_json(silent=True) or {}
    kw = {}
    if j.get("couleur") in COULEURS:
        kw["couleur"] = j["couleur"]
    if isinstance(j.get("auto"), bool):
        kw["auto"] = j["auto"]
    if isinstance(j.get("duree"), int) and 10 <= j["duree"] <= 3600:
        kw["duree"] = j["duree"]
    if not kw:
        return erreur("aucun réglage valide")
    etat.maj(**kw)
    return jsonify({"ok": True})


@app.post("/api/message")
def api_message():
    texte = str((request.get_json(silent=True) or {}).get("texte", "")).strip()[:400]
    if not texte:
        return erreur("message vide")
    etat.maj(message=texte, scene="message", msg_n=time.time())
    return jsonify({"ok": True})


@app.post("/api/image")
def api_image():
    f = request.files.get("image")
    if not f:
        return erreur("aucun fichier")
    tmp = FICHIER_IMAGE + ".tmp.png"
    try:
        S.preparer_image(f.stream, tmp)
    except Exception:
        return erreur("format d'image non reconnu (utilise JPEG ou PNG)")
    os.replace(tmp, FICHIER_IMAGE)
    etat.maj(scene="image")
    return jsonify({"ok": True})


@app.post("/api/systeme")
def api_systeme():
    action = (request.get_json(silent=True) or {}).get("action")
    cmd = {"arret": "poweroff", "redemarrage": "reboot"}.get(action)
    if not cmd:
        return erreur("action inconnue")
    etat.maj(sauver=False, scene="_" + action)
    if not APERCU:
        threading.Timer(4, lambda: subprocess.run(["systemctl", cmd])).start()
    return jsonify({"ok": True})


def main():
    global afficheur
    sortie = Apercu(APERCU) if APERCU else Framebuffer()
    afficheur = Afficheur(etat, sortie)
    afficheur.start()
    app.run(host="0.0.0.0", port=PORT, threaded=True)


if __name__ == "__main__":
    main()
