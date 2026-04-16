from PIL import Image, ImageDraw

def make_icon(size, filename):
    img = Image.new("RGBA", (size, size), (15, 15, 26, 255))
    draw = ImageDraw.Draw(img)
    
    cx, cy = size // 2, size // 2
    r = size // 3
    
    # Outer brain ellipse
    draw.ellipse([cx-r, cy-r//1.2, cx+r, cy+r//1.2], outline=(0,255,136), width=max(2, size//60))
    # Inner ellipse
    ri = r // 1.7
    draw.ellipse([cx-ri, cy-ri//1.2, cx+ri, cy+ri//1.2], outline=(0,255,136), width=max(1, size//90))
    # Cross lines
    draw.line([cx, cy-r, cx, cy+r], fill=(0,255,136), width=max(1, size//90))
    draw.line([cx-r, cy, cx+r, cy], fill=(0,255,136), width=max(1, size//90))
    # Bottom dot
    dot = size // 25
    draw.ellipse([cx-dot, cy+r+dot, cx+dot, cy+r+dot*3], fill=(0,255,136))
    
    img.save(filename)
    print(f"✅ Saved {filename}")

make_icon(192, "static/icons/icon-192.png")
make_icon(512, "static/icons/icon-512.png")
