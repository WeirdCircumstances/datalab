import io
from PIL import Image
import segno

# out = io.BytesIO()

#qrcode = segno.make("https://sensebox.de/")
#qrcode.save(out, scale=5, border=0, kind='png')

# segno.make('sensebox.de', error='h').save(out, scale=10, kind='png')
#
# out.seek(0)  # Important to let Pillow load the PNG
# img = Image.open(out)
# img = img.convert('RGB')  # Ensure colors for the output
# img_width, img_height = img.size
# logo_max_size = 130  # May use a fixed value as well
# logo_img = Image.open('./sensebox/static/logo/Sechseck-mit-Biene.png')  # The logo
# # Resize the logo to logo_max_size
# logo_img.thumbnail((logo_max_size, logo_max_size), Image.Resampling.LANCZOS)
# # Calculate the center of the QR code
# box = ((img_width - logo_img.size[0]) // 2, (img_height - logo_img.size[1]) // 2)
# img.paste(logo_img, box)
# img.save('qrcode_with_logo.png')

# Erstellen des QR-Codes
qr = segno.make('https://sensebox.de', error='h')
print(qr.designator)
print(qr.mode)

out = io.BytesIO()
qr.save(out, scale=10, kind='png')

# Zurück zum Anfang des BytesIO-Objekts
out.seek(0)

# Öffnen des QR-Codes
img = Image.open(out).convert('RGBA')  # RGBA für Transparenz
img_width, img_height = img.size

# Öffnen und anpassen des Logos
logo_img = Image.open('./sensebox/static/logo/Sechseck-mit-Biene.png').convert('RGBA')
logo_max_size = 195
logo_img.thumbnail((logo_max_size, logo_max_size), Image.Resampling.LANCZOS)

# Berechnung der Position des Logos
box = ((img_width - logo_img.size[0]) // 2, (img_height - logo_img.size[1]) // 2)

# Einfügen des Logos in den QR-Code
img.paste(logo_img, box, logo_img)  # Die dritte Argumentation ist die Maske für Transparenz

# Speichern des Ergebnisses
img.save('qrcode_with_logo.png')