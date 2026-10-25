"""Brand image assets (app/Images), prepared for use inside Tkinter.

Two Tk limitations shape everything in here:

1. ``tk.PhotoImage`` only reads GIF/PNG/PPM, and trusts the file extension
   to tell it which. These are camera photos that have been renamed by hand
   more than once -- currently ``.png`` files that still hold JPEG bytes --
   so they go through Pillow, which sniffs the real format, and come back as
   ``ImageTk.PhotoImage``.
2. Tk widgets have no per-widget opacity. A "translucent" surface is
   therefore not translucent at all -- it is an ordinary opaque image that
   Pillow blended against the theme colour *before* it was ever displayed.
   That is what :meth:`AssetStore.backdrop` and :meth:`AssetStore.scrim` do.

Tk also garbage-collects an image the moment the last Python reference to it
goes away, blanking whatever widget was showing it. Every image handed out
here is therefore cached on the store, which the app keeps alive for its
whole run.

Every accessor returns ``None`` instead of raising when Pillow is missing or
a file has been moved or renamed, so the app quietly falls back to its plain
text-and-colour chrome rather than failing to start.
"""

import os

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageTk
    PIL_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only on a bare install
    PIL_AVAILABLE = False


# Logical name -> the file's base name in app/Images, WITHOUT an extension.
# These files get re-saved and renamed by hand (they have already been both
# .jpeg and .png, and at one point were .png holding JPEG bytes), so they are
# matched on stem alone and the real format is sniffed by Pillow rather than
# trusted from the suffix. Tk's own PhotoImage would choke on that mismatch,
# which is one more reason everything here goes through Pillow.
STEMS = {
    "logo": "logo",
    "icon": "icon",
    "owner": "admin,owner",
}

# Suffixes worth picking up if the folder holds several copies of one image.
EXT_PRIORITY = (".png", ".jpeg", ".jpg", ".webp", ".bmp", ".gif")


def _hex_to_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


class AssetStore:
    """Loads the brand images once and hands out theme-matted Tk images."""

    def __init__(self, app_dir):
        # The folder has been spelled both "Images" and "images" at different
        # points, and that matters the moment this runs on a case-sensitive
        # filesystem, so resolve it by listing the parent rather than by
        # guessing a casing.
        self.dir = None
        for entry in ("Images", "images"):
            candidate = os.path.join(app_dir, entry)
            if os.path.isdir(candidate):
                self.dir = candidate
                break
        self._sources = {}
        self._cache = {}
        self._paths = self._index_files()

    def _index_files(self):
        """Map each known stem to a file on disk, case-insensitively.

        Windows treats app/Images and app/images as one folder while Linux
        does not, and the stems themselves have been capitalised
        inconsistently, so the directory is listed once and matched in
        lowercase instead of building paths from guessed spellings.
        """
        found = {}
        if self.dir is None:
            return found
        try:
            entries = os.listdir(self.dir)
        except OSError:
            return found
        for key, stem in STEMS.items():
            best, best_rank = None, len(EXT_PRIORITY)
            for entry in entries:
                name, ext = os.path.splitext(entry)
                if name.lower() != stem:
                    continue
                rank = (EXT_PRIORITY.index(ext.lower())
                        if ext.lower() in EXT_PRIORITY else len(EXT_PRIORITY) - 1)
                if rank < best_rank:
                    best, best_rank = os.path.join(self.dir, entry), rank
            if best:
                found[key] = best
        return found

    @property
    def available(self):
        return PIL_AVAILABLE and bool(self._paths)

    def _source(self, name):
        """The original Pillow image, loaded at most once per run."""
        if not self.available:
            return None
        if name not in self._sources:
            path = self._paths.get(name)
            try:
                img = Image.open(path)
                img.load()
                # Flatten any alpha onto white rather than letting Pillow drop
                # it silently, so a genuinely transparent PNG does not come
                # back with black fringing around the subject.
                if img.mode in ("RGBA", "LA", "P"):
                    img = img.convert("RGBA")
                    flat = Image.new("RGB", img.size, (255, 255, 255))
                    flat.paste(img, (0, 0), img)
                    img = flat
                self._sources[name] = img.convert("RGB")
            except Exception:
                self._sources[name] = None
        return self._sources[name]

    @staticmethod
    def _cover(img, size):
        """Scale and centre-crop so the image fills `size` without distortion
        (the same idea as CSS background-size: cover)."""
        target_w, target_h = size
        src_w, src_h = img.size
        scale = max(target_w / src_w, target_h / src_h)
        new = img.resize((max(1, int(src_w * scale)), max(1, int(src_h * scale))),
                         Image.LANCZOS)
        left = (new.width - target_w) // 2
        top = (new.height - target_h) // 2
        return new.crop((left, top, left + target_w, top + target_h))

    @staticmethod
    def _circle_mask(size):
        """Anti-aliased round mask. Drawn 4x and scaled down, because
        ImageDraw.ellipse has hard edges and a raw one looks visibly
        stair-stepped at the sizes these emblems are used at."""
        scale = 4
        mask = Image.new("L", (size * scale, size * scale), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size * scale - 1, size * scale - 1), fill=255)
        return mask.resize((size, size), Image.LANCZOS)

    def _circle_image(self, name, size):
        """The circular crop itself, plus its mask, as PIL objects."""
        src = self._source(name)
        if src is None:
            return None, None
        return self._cover(src, (size, size)), self._circle_mask(size)

    def circle(self, name, size, bg):
        """Circular crop of `name`, matted onto the solid colour `bg`.

        These photos carry no usable alpha, and Tk will not composite an
        image against an arbitrary widget background either, so the circle is
        flattened onto the exact surface colour it will sit on. The caller has
        to pass the right `bg` for its theme -- pass the wrong one and the
        circle shows up inside a visible square of the wrong shade. When the
        surface is itself an image rather than a flat colour, use
        :meth:`panel` instead, which composites the emblem into that image.
        """
        key = ("circle", name, size, bg)
        if key in self._cache:
            return self._cache[key]
        crop, mask = self._circle_image(name, size)
        if crop is None:
            return None
        out = Image.new("RGB", (size, size), _hex_to_rgb(bg))
        out.paste(crop, (0, 0), mask)
        photo = ImageTk.PhotoImage(out)
        self._cache[key] = photo
        return photo

    def backdrop(self, name, size, bg, opacity=0.18, blur=0):
        """`name` scaled to fill `size`, optionally blurred, then blended
        toward `bg`.

        `opacity` is how much of the photo survives: 0.0 is the flat theme
        colour, 1.0 the untouched photo. This is the stand-in for real
        transparency -- the result is an opaque image that merely looks like
        a faint photo showing through the surface behind it.
        """
        width, height = int(size[0]), int(size[1])
        if width < 1 or height < 1:
            return None
        key = ("backdrop", name, width, height, bg, round(opacity, 3), blur)
        if key in self._cache:
            return self._cache[key]
        src = self._source(name)
        if src is None:
            return None
        img = self._cover(src, (width, height))
        if blur:
            img = img.filter(ImageFilter.GaussianBlur(blur))
        solid = Image.new("RGB", (width, height), _hex_to_rgb(bg))
        photo = ImageTk.PhotoImage(Image.blend(solid, img, max(0.0, min(1.0, opacity))))
        self._cache[key] = photo
        return photo

    def scrim(self, name, size, bg, photo_opacity=0.10, blur=9, offset=(0, 0)):
        """A card-sized panel cut from the same backdrop the card sits on, so
        the card reads as frosted glass over the photo rather than as an
        opaque block dropped on top of it.

        `offset` is the card's position within that backdrop, which is what
        keeps the visible sliver of photo lined up with the surrounding page.
        """
        width, height = int(size[0]), int(size[1])
        if width < 1 or height < 1:
            return None
        key = ("scrim", name, width, height, bg, round(photo_opacity, 3), blur, offset)
        if key in self._cache:
            return self._cache[key]
        src = self._source(name)
        if src is None:
            return None
        # Render the full backdrop first, then cut the card's rectangle out of
        # it, so the photo continues seamlessly underneath the card.
        full_w = width + abs(offset[0]) * 2 + 2
        full_h = height + abs(offset[1]) * 2 + 2
        img = self._cover(src, (full_w, full_h))
        if blur:
            img = img.filter(ImageFilter.GaussianBlur(blur))
        left = max(0, min(full_w - width, (full_w - width) // 2 + offset[0]))
        top = max(0, min(full_h - height, (full_h - height) // 2 + offset[1]))
        img = img.crop((left, top, left + width, top + height))
        solid = Image.new("RGB", (width, height), _hex_to_rgb(bg))
        photo = ImageTk.PhotoImage(
            Image.blend(solid, img, max(0.0, min(1.0, photo_opacity))))
        self._cache[key] = photo
        return photo

    def panel(self, name, size, bg, photo_opacity=0.13, blur=14,
              emblem=None, emblem_size=66, emblem_top=20):
        """A frosted panel with an optional round emblem baked into it.

        Compositing the emblem here rather than stacking a separate circle
        widget on top is the whole point: the panel is an image, not a flat
        colour, so a separately-matted circle would sit in a square of
        mismatched shade. Done in Pillow, the emblem lands on the real pixels
        behind it and the edge disappears.
        """
        width, height = int(size[0]), int(size[1])
        if width < 1 or height < 1:
            return None
        key = ("panel", name, width, height, bg, round(photo_opacity, 3), blur,
               emblem, emblem_size, emblem_top)
        if key in self._cache:
            return self._cache[key]
        src = self._source(name)
        if src is None:
            return None
        img = self._cover(src, (width, height))
        if blur:
            img = img.filter(ImageFilter.GaussianBlur(blur))
        solid = Image.new("RGB", (width, height), _hex_to_rgb(bg))
        out = Image.blend(solid, img, max(0.0, min(1.0, photo_opacity)))
        if emblem:
            crop, mask = self._circle_image(emblem, emblem_size)
            if crop is not None:
                out.paste(crop, ((width - emblem_size) // 2, emblem_top), mask)
        photo = ImageTk.PhotoImage(out)
        self._cache[key] = photo
        return photo

    def average_color(self, name):
        """The photo's overall average colour, as an ``#rrggbb`` string.

        Used to frost the card surfaces. A card cannot show the photo through
        itself -- its child labels are opaque and would punch solid
        rectangles through any image behind them -- so instead every surface
        is tinted toward the colour of the photo it sits on. The result reads
        as translucent because the cards and the visible backdrop share a
        cast, which is the cue the eye actually reads as "see-through".
        """
        key = ("avg", name)
        if key in self._cache:
            return self._cache[key]
        src = self._source(name)
        if src is None:
            return None
        # A 1x1 resize IS the mean of every pixel, and far cheaper than
        # walking the image.
        r, g, b = src.resize((1, 1), Image.LANCZOS).getpixel((0, 0))
        value = "#%02X%02X%02X" % (r, g, b)
        self._cache[key] = value
        return value

    def window_icon(self, size=64):
        """Square image for tk's iconphoto(), which needs a PhotoImage rather
        than the .ico file Windows wants for iconbitmap()."""
        key = ("winicon", size)
        if key in self._cache:
            return self._cache[key]
        src = self._source("icon")
        if src is None:
            return None
        photo = ImageTk.PhotoImage(self._cover(src, (size, size)))
        self._cache[key] = photo
        return photo

    def release_theme_images(self):
        """Drop cached images so a theme switch re-mattes them against the new
        surface colours instead of reusing ones baked for the old palette."""
        self._cache.clear()
