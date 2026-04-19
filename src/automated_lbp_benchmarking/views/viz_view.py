
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
        Render a summary and top 5 matches as text (compact format). No giant images.
        """
        from PIL import Image, ImageDraw, ImageFont

        models = list(models)[:5]  # Cap at 5 images
        if not models:
            return

        # Try to load a default font
        try:
            font = ImageFont.truetype("arial.ttf", 14)
            font_small = ImageFont.truetype("arial.ttf", 10)
        except Exception:
            font = ImageFont.load_default()
            font_small = ImageFont.load_default()

        pad = 10
        line_height = 18
        max_width = 1000
        
        # Build text content
        text_lines = []
        
        # Add summary
        summary_lines = summary_lines or []
        args_lines = []
        if args:
            args_lines.append("Arguments used:")
            for k, v in args.items():
                args_lines.append(f"  {k}: {v}")
            args_lines.append("")
        
        text_lines.extend(args_lines + summary_lines)
        text_lines.append("=" * 80)
        
        # Add each match (top 5)
        for idx, m in enumerate(models):
            text_lines.append(f"\n[Match {idx + 1}] Index: {m.index}")
            text_lines.append("Original: " + ", ".join(f"{k}={v}" for k, v in m.original_meta.items()))
            
            matched_images = m.matched_images if m.matched_images is not None else ([m.matched_image] if m.matched_image else [])
            if matched_images:
                text_lines.append(f"Matched: {len(matched_images)} match(es)")
                if m.matched_meta_list:
                    for i, meta in enumerate(m.matched_meta_list):
                        dist_str = ""
                        if m.matched_distances and i < len(m.matched_distances):
                            dist_val = m.matched_distances[i]
                            dist_str = f" (distance: {float(dist_val):.6f})" if isinstance(dist_val, (int, float)) else f" (distance: {dist_val})"
                        meta_str = ", ".join(f"{k}={v}" for k, v in meta.items())
                        text_lines.append(f"  {i+1}. {meta_str}{dist_str}")
            else:
                text_lines.append("Matched: None")
            text_lines.append("")
        
        # Estimate total height
        total_height = pad + len(text_lines) * line_height + pad
        
        # Create image
        img = Image.new("RGB", (max_width, total_height), "white")
        draw = ImageDraw.Draw(img)
        
        y = pad
        for line in text_lines:
            draw.text((pad, y), line, fill="black", font=font_small)
            y += line_height
        
        # Save as PDF
        try:
            img.save(pdf_path, "PDF")
        except Exception as e:
            print(f"Warning: Could not save PDF: {e}")

    def show(self, models: Iterable[MatchItemModel], max_size: int = 300) -> None:
        models = list(models)  # No cap for runtime visualization
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
            matched_images = m.matched_images if m.matched_images is not None else ([m.matched_image] if m.matched_image else [])
            has_tolerance_matches = m.matched_images is not None and len(m.matched_images) > 0
            
            frame = ttk.Frame(scrollable_frame, padding=6, relief="ridge")
            frame.pack(fill="x", padx=6, pady=6)

            if has_tolerance_matches:
                # Multi-match layout (tolerance mode): show in grid with wrapping
                left_photo = make_thumb(m.original_image)
                photo_refs.append(left_photo)

                left_label = ttk.Label(frame)
                if left_photo:
                    left_label.configure(image=left_photo)
                else:
                    left_label.configure(text="(no image)")
                left_label.grid(row=0, column=0, padx=8, pady=4, rowspan=2)

                # Original metadata
                orig_meta_text = "\n".join(f"{k}: {v}" for k, v in m.original_meta.items())
                ttk.Label(frame, text=orig_meta_text, justify="left", anchor="w").grid(
                    row=0, column=1, sticky="w", padx=4
                )

                # Matched images in a grid with wrapping (max 3 per row)
                matched_frame = ttk.Frame(frame)
                matched_frame.grid(row=1, column=1, sticky="w", padx=4, pady=4)
                
                images_per_row = 3
                for idx, match_img in enumerate(matched_images):
                    match_thumb_photo = make_thumb(match_img) if isinstance(match_img, Image.Image) else None
                    photo_refs.append(match_thumb_photo)
                    
                    row_idx = idx // images_per_row
                    col_idx = idx % images_per_row
                    
                    col_frame = ttk.Frame(matched_frame)
                    col_frame.grid(row=row_idx, column=col_idx, padx=2, pady=2)
                    
                    match_label = ttk.Label(col_frame)
                    if match_thumb_photo:
                        match_label.configure(image=match_thumb_photo)
                    else:
                        match_label.configure(text="(no image)")
                    match_label.pack()
                    
                    # Distance underneath
                    dist_str = "(no distance)"
                    if m.matched_distances and idx < len(m.matched_distances):
                        dist_val = m.matched_distances[idx]
                        if isinstance(dist_val, (int, float)):
                            dist_str = f"{float(dist_val):.6f}"
                        else:
                            dist_str = str(dist_val)
                    ttk.Label(col_frame, text=dist_str, font=("TkDefaultFont", 9)).pack()
            else:
                # Single match layout (original mode): side by side
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
        
