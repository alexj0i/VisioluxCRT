"""Moteur d'affichage Visiolux : sortie composite (/dev/fb0) + terminal rétro.

Tout est dessiné en 720x576 (PAL). Les pixels PAL sont un peu plus larges que
hauts (rapport PAR) : on en tient compte pour les cercles.
"""
import fcntl
import os
import subprocess
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 720, 576
PAR = 16 / 15            # largeur/hauteur d'un pixel PAL affiché en 4:3
MX, MY = 58, 46          # marges : zone réellement visible du CRT (surbalayage)
ZONE = (MX, MY, W - MX, H - MY)

COULEURS = {
    "vert": (70, 255, 120),
    "ambre": (255, 176, 40),
    "blanc": (235, 235, 235),
}

POLICES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
]
_polices = {}


def police(taille):
    if taille not in _polices:
        for p in POLICES:
            if os.path.exists(p):
                _polices[taille] = ImageFont.truetype(p, taille)
                break
        else:
            _polices[taille] = ImageFont.load_default(taille)
    return _polices[taille]


def attenuer(c, f):
    return tuple(int(v * f) for v in c)


# --------------------------------------------------------------------------
# Sorties
# --------------------------------------------------------------------------
class Framebuffer:
    """Écrit une image PIL dans /dev/fb0 (16 ou 32 bits par pixel)."""

    KDSETMODE, KD_GRAPHICS, KD_TEXT = 0x4B3A, 1, 0

    def __init__(self, dev="/dev/fb0", tty="/dev/tty1"):
        base = "/sys/class/graphics/" + os.path.basename(dev)
        self.w, self.h = W, H
        try:  # ex. "U:720x576i-50"
            mode = open(base + "/modes").readline().strip().split(":")[1]
            self.w, self.h = (int(v) for v in mode.split("i")[0].split("p")[0].split("-")[0].split("x"))
        except Exception:
            vw, vh = open(base + "/virtual_size").read().strip().split(",")
            self.w, self.h = int(vw), int(vh)
        self.bpp = int(open(base + "/bits_per_pixel").read())
        self.stride = int(open(base + "/stride").read())
        self.fb = open(dev, "r+b", buffering=0)
        # Empêche la console texte de dessiner par-dessus l'image
        self.tty = None
        try:
            subprocess.run(["chvt", tty[-1]], check=False)
            self.tty = os.open(tty, os.O_RDWR)
            fcntl.ioctl(self.tty, self.KDSETMODE, self.KD_GRAPHICS)
        except OSError:
            pass

    def afficher(self, img):
        if img.size != (self.w, self.h):
            img = img.resize((self.w, self.h), Image.BILINEAR)
        if self.bpp == 32:
            data = img.tobytes("raw", "BGRX")
            largeur = self.w * 4
        else:  # RGB565
            a = np.asarray(img, dtype=np.uint16)
            px = ((a[..., 0] >> 3) << 11) | ((a[..., 1] >> 2) << 5) | (a[..., 2] >> 3)
            data = px.astype("<u2").tobytes()
            largeur = self.w * 2
        if self.stride != largeur:
            buf = bytearray(self.stride * self.h)
            for y in range(self.h):
                buf[y * self.stride:y * self.stride + largeur] = data[y * largeur:(y + 1) * largeur]
            data = bytes(buf)
        self.fb.seek(0)
        self.fb.write(data)

    def fermer(self):
        if self.tty is not None:
            try:
                fcntl.ioctl(self.tty, self.KDSETMODE, self.KD_TEXT)
            except OSError:
                pass


class Apercu:
    """Sortie de test : enregistre une image PNG par seconde dans un dossier."""

    def __init__(self, dossier):
        self.dossier = dossier
        os.makedirs(dossier, exist_ok=True)
        self.dernier = 0

    def afficher(self, img):
        if time.monotonic() - self.dernier >= 1:
            self.dernier = time.monotonic()
            img.save(os.path.join(self.dossier, "apercu.png"))

    def fermer(self):
        pass


# --------------------------------------------------------------------------
# Terminal texte
# --------------------------------------------------------------------------
INVERSE, ATTENUE = "\x01", "\x02"   # à mettre en début de ligne


class Terminal:
    """Grille de texte. Une ligne commençant par INVERSE s'affiche en vidéo
    inverse, par ATTENUE en couleur atténuée."""

    def __init__(self, taille=26, interligne=30, zone=ZONE):
        self.f = police(taille)
        self.cw = self.f.getlength("M")
        self.lh = interligne
        self.zone = zone
        self.cols = int((zone[2] - zone[0]) // self.cw)
        self.rows = int((zone[3] - zone[1]) // self.lh)
        self.cache = {}
        self.effacer()

    def effacer(self):
        self.lignes = [["", ""]]          # [style, texte]

    def nouvelle_ligne(self):
        self.lignes.append(["", ""])
        if len(self.lignes) > self.rows:
            self.lignes = self.lignes[-self.rows:]

    def ecrire(self, texte):
        for ch in texte:
            if ch == "\n":
                self.nouvelle_ligne()
            elif ch in (INVERSE, ATTENUE) and not self.lignes[-1][1]:
                self.lignes[-1][0] = ch
            else:
                if len(self.lignes[-1][1]) >= self.cols:
                    self.nouvelle_ligne()
                self.lignes[-1][1] += ch

    def remplacer_derniere(self, texte):
        style = texte[0] if texte[:1] in (INVERSE, ATTENUE) else ""
        self.lignes[-1] = [style, texte[len(style):][: self.cols]]

    def fixer_ligne(self, i, texte):
        while len(self.lignes) <= i:
            self.lignes.append(["", ""])
        style = texte[0] if texte[:1] in (INVERSE, ATTENUE) else ""
        self.lignes[i] = [style, texte[len(style):][: self.cols]]

    def _masque(self, txt):
        """Rendu d'une ligne mis en cache : seules les lignes nouvelles sont
        recalculées (le rendu des polices est lent sur un Pi 3)."""
        m = self.cache.get(txt)
        if m is None:
            if len(self.cache) > 300:
                self.cache.clear()
            m = Image.new("L", (int(self.cols * self.cw) + 2, self.lh))
            ImageDraw.Draw(m).text((0, 0), txt, font=self.f, fill=255)
            self.cache[txt] = m
        return m

    def dessiner(self, img, d, couleur, t, curseur=True):
        x0, y0 = self.zone[0], self.zone[1]
        for i, (style, txt) in enumerate(self.lignes):
            y = y0 + i * self.lh
            if style == INVERSE:
                d.rectangle([x0 - 4, y, x0 + self.cols * self.cw + 4, y + self.lh - 2], fill=couleur)
                img.paste((0, 0, 0), (int(x0), int(y)), self._masque(txt))
            elif txt:
                img.paste(attenuer(couleur, 0.45) if style == ATTENUE else couleur,
                          (int(x0), int(y)), self._masque(txt))
        if curseur and int(t * 2.5) % 2 == 0:
            cx = x0 + len(self.lignes[-1][1]) * self.cw
            cy = y0 + (len(self.lignes) - 1) * self.lh
            d.rectangle([cx + 1, cy + 4, cx + self.cw - 2, cy + self.lh - 4], fill=couleur)


class Lecteur:
    """Exécute un script de terminal. Le script est un générateur qui produit
    des commandes :
      ("taper", texte, car_par_seconde)   frappe progressive
      ("afficher", texte)                 affichage immédiat
      ("pause", secondes)
      ("effacer",)
      ("barre", libelle, secondes)        barre de progression animée
      ("compter", modele, debut, fin, secondes)   modele contient {}
      ("ligne", index, texte)             remplace une ligne précise
    """

    def __init__(self, terminal, script):
        self.term = terminal
        self.script = script
        self.reset()

    def reset(self):
        self.term.effacer()
        self.gen = self.script()
        self.cmd = None

    def avancer(self, dt):
        for _ in range(200):                 # commandes instantanées enchaînées
            if self.cmd is None:
                try:
                    self.cmd = next(self.gen)
                except StopIteration:
                    self.reset()
                    return
                self.e = 0.0
                self.pos = 0
            c = self.cmd
            k = c[0]
            if k == "afficher":
                self.term.ecrire(c[1])
                self.cmd = None
                continue
            if k == "effacer":
                self.term.effacer()
                self.cmd = None
                continue
            if k == "ligne":
                self.term.fixer_ligne(c[1], c[2])
                self.cmd = None
                continue
            self.e += dt
            if k == "taper":
                n = min(len(c[1]), int(self.e * c[2]))
                self.term.ecrire(c[1][self.pos:n])
                self.pos = n
                if n >= len(c[1]):
                    self.cmd = None
            elif k == "pause":
                if self.e >= c[1]:
                    self.cmd = None
            elif k == "barre":
                frac = min(1.0, self.e / c[2])
                larg = self.term.cols - len(c[1]) - 8
                plein = int(frac * larg)
                self.term.remplacer_derniere(f"{c[1]}[{'#' * plein}{'.' * (larg - plein)}] {int(frac * 100):3d}%")
                if frac >= 1:
                    self.term.nouvelle_ligne()
                    self.cmd = None
            elif k == "compter":
                frac = min(1.0, self.e / c[4])
                self.term.remplacer_derniere(c[1].format(int(c[2] + (c[3] - c[2]) * frac)))
                if frac >= 1:
                    self.term.nouvelle_ligne()
                    self.cmd = None
            return


class Grille:
    """Affichage rapide d'une grille de caractères (art ASCII) : chaque glyphe
    est rendu une seule fois, puis l'image est assemblée avec numpy."""

    def __init__(self, caracteres, taille=14, cw=9, lh=15):
        f = police(taille)
        self.cw, self.lh = cw, lh
        self.index = {c: i for i, c in enumerate(caracteres)}
        g = []
        for c in caracteres:
            m = Image.new("L", (cw, lh))
            ImageDraw.Draw(m).text((cw / 2, lh / 2), c, font=f, fill=255, anchor="mm")
            g.append(np.asarray(m, dtype=np.float32) / 255)
        self.glyphes = np.stack(g)

    def codes(self, c):
        return self.index[c]

    def dessiner(self, img, x0, y0, codes, niveau, couleur):
        """codes : tableau (lignes, colonnes) d'indices de caractères ;
        niveau : luminosité 0..1 par case."""
        r, c = codes.shape
        g = self.glyphes[codes] * niveau[..., None, None]
        m = g.transpose(0, 2, 1, 3).reshape(r * self.lh, c * self.cw)
        rgb = (m[..., None] * np.array(couleur, dtype=np.float32)).astype(np.uint8)
        img.paste(Image.fromarray(rgb), (int(x0), int(y0)))
