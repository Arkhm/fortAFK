"""Gera o icone.ico do FortniteAFK usando apenas Pillow."""

from pathlib import Path

from PIL import Image, ImageDraw


def main():
    # Desenha em tamanho maior para suavizar as bordas ao reduzir.
    imagem = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    desenho = ImageDraw.Draw(imagem)
    desenho.rounded_rectangle((16, 16, 1008, 1008), radius=208, fill="#1b1c20")
    desenho.polygon([(368, 272), (368, 752), (752, 512)], fill="#f5c542")
    desenho.ellipse((728, 104, 920, 296), fill="#e5484d")
    imagem = imagem.resize((256, 256), Image.Resampling.LANCZOS)

    # Salva ao lado deste script, mesmo se ele for iniciado de outra pasta.
    destino = Path(__file__).resolve().with_name("icone.ico")
    tamanhos = [(lado, lado) for lado in (16, 24, 32, 48, 64, 128, 256)]
    imagem.save(destino, format="ICO", sizes=tamanhos)
    print(f"Ícone criado: {destino}")


if __name__ == "__main__":
    main()
