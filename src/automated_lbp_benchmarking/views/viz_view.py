
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Iterable, Optional

from PIL import Image, ImageTk

from ..models.viz_model import MatchItemModel



class MatchesView:
    def __init__(self, title: str = "LBP Matches") -> None:
        self._title = title

    def save_as_pdf(self, models: Iterable[MatchItemModel], pdf_path: str, max_size: int = 300, args: dict = None, summary_lines: list = None) -> None:
        """
        Render a summary and each match as an image, stack vertically, and save as PDF. No screenshots or Tkinter required.
        """
        from PIL import Image, ImageDraw, ImageFont
        import math

        models = list(models)
        if not models:
            return

        # Try to load a default font
        try:
            font = ImageFont.truetype("arial.ttf", 16)
        except Exception:
            font = ImageFont.load_default()

        pad = 16
        img_size = max_size
        text_width = 600
        row_height = img_size + 2 * pad
        row_width = 2 * (img_size + pad) + text_width + 3 * pad

        # --- Render summary section ---
        summary_lines = summary_lines or []
        args_lines = []
        if args:
            args_lines.append("Arguments used:")
            for k, v in args.items():
                args_lines.append(f"  {k}: {v}")
            args_lines.append("")
        summary_block = args_lines + summary_lines
        # Estimate height for summary block
        dummy_img = Image.new("RGB", (row_width, 100), "white")
        dummy_draw = ImageDraw.Draw(dummy_img)
        summary_height = pad
        for line in summary_block:
            bbox = dummy_draw.textbbox((pad, summary_height), line, font=font)
            line_height = bbox[3] - bbox[1]
            summary_height += line_height + 2
        summary_height += pad
        summary_img = Image.new("RGB", (row_width, summary_height), "white")
        draw = ImageDraw.Draw(summary_img)
        y = pad
        for line in summary_block:
            draw.text((pad, y), line, fill="black", font=font)
            bbox = draw.textbbox((pad, y), line, font=font)
            line_height = bbox[3] - bbox[1]
            y += line_height + 2

        # --- Render each match as an image row ---
        rows = []
        for m in models:
            row_img = Image.new("RGB", (row_width, row_height), "white")
            draw = ImageDraw.Draw(row_img)

            # Left image
            if m.original_image:
                left_img = m.original_image.copy()
                left_img.thumbnail((img_size, img_size), Image.LANCZOS)
                row_img.paste(left_img, (pad, pad))
            else:
                draw.rectangle([pad, pad, pad+img_size, pad+img_size], outline="black")
                draw.text((pad+10, pad+img_size//2), "(no image)", fill="black", font=font)

            # Right image
            if m.matched_image:
                right_img = m.matched_image.copy()
                right_img.thumbnail((img_size, img_size), Image.LANCZOS)
                row_img.paste(right_img, (pad*2+img_size, pad))
            else:
                draw.rectangle([pad*2+img_size, pad, pad*2+2*img_size, pad+img_size], outline="black")
                draw.text((pad*2+img_size+10, pad+img_size//2), "(no match)", fill="black", font=font)

            # Text info
            info_lines = []
            info_lines.append(f"Index: {m.index}")
            info_lines.append("-- Original --")
            for k, v in m.original_meta.items():
                info_lines.append(f"{k}: {v}")
            info_lines.append("")
            info_lines.append("-- Matched --")
            if m.matched_meta:
                for k, v in m.matched_meta.items():
                    info_lines.append(f"{k}: {v}")
            else:
                info_lines.append("(no match)")
            info_lines.append("")
            info_lines.append(f"Distance Metric: {m.metric_name}")
            if m.distance is None:
                dist_line = "Distance: None"
            elif isinstance(m.distance, (int, float)):
                dist_line = f"Distance: {float(m.distance):.6f}"
            else:
                dist_line = f"Distance: {m.distance}"
            info_lines.append(dist_line)

            text_x = pad*3 + 2*img_size
            text_y = pad

            for line in info_lines:
                draw.text((text_x, text_y), line, fill="black", font=font)
                bbox = draw.textbbox((text_x, text_y), line, font=font)
                line_height = bbox[3] - bbox[1]
                text_y += line_height + 2

            rows.append(row_img)

        # Stack summary and all rows vertically
        total_height = summary_img.height + len(rows) * row_height
        pdf_img = Image.new("RGB", (row_width, total_height), "white")
        pdf_img.paste(summary_img, (0, 0))
        for i, row in enumerate(rows):
            pdf_img.paste(row, (0, summary_img.height + i * row_height))

        # Save as PDF
        pdf_img.save(pdf_path, "PDF", resolution=100.0)

    def show(self, models: Iterable[MatchItemModel], max_size: int = 300) -> None:
        models = list(models)
        if not models:
            print("No items to visualize")
            return

        root = tk.Tk()
        root.title(self._title)

        canvas = tk.Canvas(root)
        scrollbar = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Keep PhotoImage references alive for the duration of the UI
        photo_refs = []

        def make_thumb(img: Optional[Image.Image]) -> Optional[ImageTk.PhotoImage]:
            if img is None:
                return None
            im = img.copy()
            im.thumbnail((max_size, max_size), Image.LANCZOS)
            return ImageTk.PhotoImage(im)

        for m in models:
            frame = ttk.Frame(scrollable_frame, padding=6, relief="ridge")
            frame.pack(fill="x", padx=6, pady=6)

            left_photo = make_thumb(m.original_image)
            right_photo = make_thumb(m.matched_image)
            photo_refs.append((left_photo, right_photo))

            left_label = ttk.Label(frame)
            if left_photo:
                left_label.configure(image=left_photo)
            else:
                left_label.configure(text="(no image)")
            left_label.grid(row=0, column=0, rowspan=2, padx=8)

            right_label = ttk.Label(frame)
            if right_photo:
                right_label.configure(image=right_photo)
            else:
                right_label.configure(text="(no match)")
            right_label.grid(row=0, column=1, rowspan=2, padx=8)

            info_lines = []
            info_lines.append(f"Index: {m.index}")
            info_lines.append("-- Original --")
            for k, v in m.original_meta.items():
                info_lines.append(f"{k}: {v}")
            info_lines.append("")
            info_lines.append("-- Matched --")
            if m.matched_meta:
                for k, v in m.matched_meta.items():
                    info_lines.append(f"{k}: {v}")
            else:
                info_lines.append("(no match)")
            info_lines.append("")
            info_lines.append(f"Distance Metric: {m.metric_name}")

            if m.distance is None:
                dist_line = "Distance: None"
            elif isinstance(m.distance, (int, float)):
                dist_line = f"Distance: {float(m.distance):.6f}"
            else:
                dist_line = f"Distance: {m.distance}"
            info_lines.append(dist_line)

            info_text = "\n".join(info_lines)
            ttk.Label(frame, text=info_text, justify="left", anchor="w", wraplength=600).grid(
                row=0, column=2, sticky="w"
            )

        root.mainloop()
        
