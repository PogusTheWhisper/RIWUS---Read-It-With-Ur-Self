import fitz  # PyMuPDF
import tkinter as tk
from tkinter import filedialog, scrolledtext
from PIL import Image, ImageTk
import time
import json
import os
import os.path
import threading
from openai import OpenAI  # Assuming you have the OpenAI Python library installed
import sys

class StdoutRedirector:
    def __init__(self, text_widget):
        self.text_widget = text_widget
    
    def write(self, text):
        self.text_widget.insert(tk.END, text)
        self.text_widget.see(tk.END)  # Auto-scroll to the end
    
    def flush(self):
        pass

class PDFViewer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("RIWUS - Read It With Ur(your) Self")
        
        # Main container
        self.main_frame = tk.Frame(self)
        self.main_frame.pack(fill=tk.BOTH, expand=1)
        
        # PDF Viewer area
        self.pdf_frame = tk.Frame(self.main_frame)
        self.pdf_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        
        self.canvas = tk.Canvas(self.pdf_frame)
        self.canvas.pack(fill=tk.BOTH, expand=1)
        
        self.button_frame = tk.Frame(self.pdf_frame)
        self.button_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.prev_button = tk.Button(self.button_frame, text="Previous", command=self.show_prev_page)
        self.prev_button.pack(side=tk.LEFT)
        
        self.next_button = tk.Button(self.button_frame, text="Next", command=self.show_next_page)
        self.next_button.pack(side=tk.RIGHT)
        
        self.page_label = tk.Label(self.button_frame, text="")
        self.page_label.pack(side=tk.LEFT, padx=10)
        
        self.open_button = tk.Button(self.button_frame, text="Open PDF", command=self.load_pdf)
        self.open_button.pack(side=tk.RIGHT)
        
        self.pdf_document = None
        self.current_page = 0
        self.page_time = {}  # Dictionary to store time spent per page
        self.start_time = time.time()
        self.file_name = None
        
        # Chat area
        self.chat_frame = tk.Frame(self.main_frame, width=300)
        self.chat_frame.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.chat_log = scrolledtext.ScrolledText(self.chat_frame, state=tk.DISABLED, wrap=tk.WORD)
        self.chat_log.pack(padx=10, pady=10, fill=tk.BOTH, expand=1)
        
        self.entry_frame = tk.Frame(self.chat_frame)
        self.entry_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.chat_entry = tk.Entry(self.entry_frame)
        self.chat_entry.pack(side=tk.LEFT, fill=tk.X, expand=1, padx=10, pady=10)
        self.chat_entry.bind("<Return>", self.send_message)
        
        self.send_button = tk.Button(self.entry_frame, text="Send", command=self.send_message)
        self.send_button.pack(side=tk.RIGHT, padx=10, pady=10)
        self.client = OpenAI(
        api_key='<Typhoon token>',
        base_url="https://api.opentyphoon.ai/v1",
        )
        
        # Redirect stdout to update chat log
        self.stdout_redirector = StdoutRedirector(self.chat_log)
        sys.stdout = self.stdout_redirector
        
        # Load saved page time data if exists
        self.load_saved_page_time()
    
    def load_saved_page_time(self):
        if self.file_name:
            save_file = f"{self.file_name}_page_time.json"
            if os.path.exists(save_file):
                with open(save_file, 'r') as f:
                    existing_data = json.load(f)
                    for page_num, time_spent in existing_data.items():
                        if page_num in self.page_time:
                            self.page_time[page_num] += time_spent
                        else:
                            self.page_time[page_num] = time_spent
    
    def save_page_time(self):
        if self.file_name:
            save_file = f"{self.file_name}_page_time.json"
            with open(save_file, 'w') as f:
                json.dump(self.page_time, f)
    
    def load_pdf(self):
        file_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if file_path:
            self.file_name = os.path.splitext(os.path.basename(file_path))[0]
            self.pdf_document = fitz.open(file_path)
            self.current_page = 0
            self.show_page_async(self.current_page)
    
    def show_page_async(self, page_number):
        # Using threading to load and display pages asynchronously
        if self.pdf_document:
            threading.Thread(target=self.show_page, args=(page_number,)).start()
    
    def show_page(self, page_number):
        if self.pdf_document:
            if self.current_page in self.page_time:
                self.page_time[self.current_page] += time.time() - self.start_time
            else:
                self.page_time[self.current_page] = time.time() - self.start_time
            self.start_time = time.time()
            
            page = self.pdf_document.load_page(page_number)
            pix = page.get_pixmap()
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            img = ImageTk.PhotoImage(img)
            
            # Update GUI in the main thread
            self.update_gui(lambda: self.canvas.create_image(0, 0, image=img, anchor=tk.NW))
            self.canvas.image = img
            
            self.update_gui(lambda: self.page_label.config(text=f"Page {page_number + 1} of {len(self.pdf_document)}"))
            
            try:
                with open('pages.json', 'r', encoding='utf-8') as f:
                    pages = json.load(f)
            except FileNotFoundError:
                pages = []
            
            # Check if time spent exceeds 5 seconds
            if page_number not in pages and self.page_time.get(page_number, 0) > 5:
                self.get_text_from_pdf(page_number)
    
    def setup_txt(self):
        file_name = f"{self.file_name}_page_texts.txt"
        with open(file_name, 'a', encoding='utf-8') as f:
            f.write(file_name[:-4]+'\n\n')
            
    def get_text_from_pdf(self, page_number):
        # Step 1: Read the current data from the JSON file
        try:
            with open('pages.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            data = []  # Initialize as an empty list if the file doesn't exist
            
        if self.pdf_document and page_number not in data:
            page = self.pdf_document.load_page(page_number)
            text = page.get_text()
            file_name = f"{self.file_name}_page_texts.txt"
            if os.path.exists(file_name):
                with open(file_name, 'a', encoding='utf-8') as f:
                    f.write(f'<Page {page_number+1}> ')
                    stream = self.client.chat.completions.create(
                    model="typhoon-instruct",
                    # model = "typhoon-v1.5x-70b-instruct",
                    messages=[
                        {
                            "role": "systemp",
                            "content": """
                            <หน้าที่>คุณมีหน้าที่สรุปข้อความจากหนังสือแต่ละหน้าต่อไปนี้อธิบายแต่ใจความเอาแต่สิ่งที่สำคัญ โดยไม่ต้องมีคำเกรี่นนำหรือชื่อหนังสือ และถ้าหากมีเนื้อหาไม่เพืียงพอให้ตอบว่า "-" </หย้าที่>
                            """,
                        },
                        {
                            "role": "user",
                            "content": f"{text}",
                        }
                    ],
                    max_tokens=512,
                    temperature=0,
                    top_p=0.99,
                    stream=True,
                    )

                    for chunk in stream:
                        if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                            choice = chunk.choices[0]
                            if hasattr(choice, 'delta') and hasattr(choice.delta, 'content'):
                                if choice.delta.content is not None:
                                    f.write(choice.delta.content)
                    f.write('\n\n')
            else:
                self.setup_txt()
                
            # Step 2: Append the new page number
            data.append(page_number)

            # Step 3: Write the updated data back to the JSON file
            with open('pages.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
    
    def update_gui(self, callback):
        self.after(0, callback)
    
    def show_prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.show_page_async(self.current_page)
    
    def show_next_page(self):
        if self.pdf_document and self.current_page < len(self.pdf_document) - 1:
            self.current_page += 1
            self.show_page_async(self.current_page)
    
    def run_llm_config(self, data_path, user):
        with open(data_path, 'r', encoding='utf-8') as f:
            data = f.read()
        stream = self.client.chat.completions.create(
        model="typhoon-instruct",
        # model = "typhoon-v1.5x-70b-instruct",
        messages=[
            {
                "role": "systemp",
                "content": 'คุณมีหน้าที่ตอบคำถามจากข้อมูลต่อไปนี้ ถ้าหากไม่มีข้อมูล ให้ตอบว่าไม่มีข้อมูล โดยห้ามสร้างข้อมูลเองเด็ดขาด',
            },
            {
                "role": "user",
                "content": f"""
                <ข้อมูล>
                
                {data}
                
                <คำถาม>
                
                {user}
                """,
            }
        ],
        max_tokens=512,
        temperature=0,
        top_p=0.99,
        stream=True,
        )

        for chunk in stream:
            if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                choice = chunk.choices[0]
                if hasattr(choice, 'delta') and hasattr(choice.delta, 'content'):
                    if choice.delta.content is not None:
                        self.update_chat_log(str(choice.delta.content), end='')
        self.update_chat_log(' ')
    
    def send_message(self, event=None):
        user_message = self.chat_entry.get().strip()
        file_name = f"{self.file_name}_page_texts.txt"
        if user_message:
            self.update_chat_log("You: " + user_message, end='')
            self.update_chat_log(' ')
            self.update_chat_log('LLM: ', end='')
            self.run_llm_config(file_name, user_message)
            self.update_chat_log('='*80)
        self.chat_entry.delete(0, tk.END)
        
    def update_chat_log(self, message, end='\n'):
        self.chat_log.config(state=tk.NORMAL)
        self.chat_log.insert(tk.END, message + end)
        self.chat_log.config(state=tk.DISABLED)
        self.chat_log.yview(tk.END)
    
    def on_closing(self):
        if self.pdf_document and self.current_page in self.page_time:
            self.page_time[self.current_page] += time.time() - self.start_time
        else:
            self.page_time[self.current_page] = time.time() - self.start_time
        
        self.save_page_time()
        
        # Get text from PDF for pages where time spent exceeds 5 seconds
        for page_num, time_spent in self.page_time.items():
            if time_spent > 5:
                self.get_text_from_pdf(page_num)
        
        print("Time spent on each page:")
        for page, time_spent in self.page_time.items():
            print(f"Page {page + 1}: {time_spent:.2f} seconds")
        self.destroy()

if __name__ == "__main__":
    viewer = PDFViewer()
    viewer.protocol("WM_DELETE_WINDOW", viewer.on_closing)
    viewer.mainloop()
