import os
import json
import base64
import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QTreeWidget, QTreeWidgetItem, QMessageBox, QLabel
)
from PySide6.QtCore import Qt

class BackupApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Directory to Base64 JSON Encoder/Decoder")
        self.resize(800, 600)
        
        self.selected_root = ""
        self.init_ui()
        
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Top selection layout
        top_layout = QHBoxLayout()
        self.btn_select_dir = QPushButton("1. Select Source Directory")
        self.btn_select_dir.clicked.connect(self.select_directory)
        top_layout.addWidget(self.btn_select_dir)
        
        self.lbl_path = QLabel("No directory selected")
        self.lbl_path.setWordWrap(True)
        top_layout.addWidget(self.lbl_path, 1)
        
        layout.addLayout(top_layout)
        
        # File Tree Selection UI
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["File / Folder Structure"])
        self.tree.itemChanged.connect(self.handle_item_changed)
        layout.addWidget(self.tree)
        
        # Bottom Execution Actions
        bottom_layout = QHBoxLayout()
        
        self.btn_encode = QPushButton("2. Encode Selected to JSON")
        self.btn_encode.clicked.connect(self.encode_to_json)
        bottom_layout.addWidget(self.btn_encode)
        
        self.btn_decode = QPushButton("Restore/Decode from JSON")
        self.btn_decode.clicked.connect(self.decode_from_json)
        bottom_layout.addWidget(self.btn_decode)
        
        layout.addLayout(bottom_layout)

    def select_directory(self):
        """ Opens a native directory picker dialog. """
        dir_path = QFileDialog.getExistingDirectory(self, "Select Source Directory")
        if dir_path:
            self.selected_root = os.path.normpath(dir_path)
            self.lbl_path.setText(f"Selected: {self.selected_root}")
            self.populate_tree()
            
    def populate_tree(self):
        """ Clears the tree and scans the nested directry depth recursively. """
        self.tree.blockSignals(True)
        self.tree.clear()
        
        # Root node
        root_item = QTreeWidgetItem(self.tree, [os.path.basename(self.selected_root)])
        root_item.setData(0, Qt.UserRole, self.selected_root)
        root_item.setCheckState(0, Qt.Checked)
        
        self.add_tree_nodes(self.selected_root, root_item)
        
        self.tree.expandToDepth(1)
        self.tree.blockSignals(False)

    def add_tree_nodes(self, path, parent_item):
        """ Recursively lists files/folders using fast os.scandir. """
        try:
            for entry in os.scandir(path):
                item = QTreeWidgetItem(parent_item, [entry.name])
                item.setData(0, Qt.UserRole, entry.path)
                item.setCheckState(0, parent_item.checkState(0))
                
                if entry.is_dir(follow_symlinks=False):
                    self.add_tree_nodes(entry.path, item)
        except Exception as e:
            print(f"Error scanning directory {path}: {e}")

    def handle_item_changed(self, item, column):
        """ Event handle to propagate checkbox updates upward and downward. """
        self.tree.blockSignals(True)
        state = item.checkState(column)
        
        # Force identical check states on all descendants
        self.set_children_check_state(item, state)
        # Update ancestors dynamically (PartiallyChecked / Checked / Unchecked)
        self.update_parent_check_state(item)
        
        self.tree.blockSignals(False)

    def set_children_check_state(self, item, state):
        for i in range(item.childCount()):
            child = item.child(i)
            child.setCheckState(0, state)
            self.set_children_check_state(child, state)

    def update_parent_check_state(self, item):
        parent = item.parent()
        if not parent:
            return
            
        child_count = parent.childCount()
        checked_count = 0
        partially_checked_count = 0
        
        for i in range(child_count):
            state = parent.child(i).checkState(0)
            if state == Qt.Checked:
                checked_count += 1
            elif state == Qt.PartiallyChecked:
                partially_checked_count += 1
                
        if checked_count == child_count:
            parent.setCheckState(0, Qt.Checked)
        elif checked_count > 0 or partially_checked_count > 0:
            parent.setCheckState(0, Qt.PartiallyChecked)
        else:
            parent.setCheckState(0, Qt.Unchecked)
            
        self.update_parent_check_state(parent)

    def get_checked_files(self, item, file_list):
        """ Walks the visible UI tree to find explicitly checked files. """
        path = item.data(0, Qt.UserRole)
        if os.path.isfile(path) and item.checkState(0) == Qt.Checked:
            file_list.append(path)
            
        for i in range(item.childCount()):
            self.get_checked_files(item.child(i), file_list)

    def encode_to_json(self):
        """ Converts the checked file items into base64 and bundles them inside JSON. """
        if not self.selected_root or self.tree.topLevelItemCount() == 0:
            QMessageBox.warning(self, "Warning", "Please select a directory first.")
            return
            
        file_list = []
        self.get_checked_files(self.tree.topLevelItem(0), file_list)
        
        if not file_list:
            QMessageBox.warning(self, "Warning", "No files selected to encode.")
            return
            
        save_path, _ = QFileDialog.getSaveFileName(self, "Save JSON File", "", "JSON Files (*.json)")
        if not save_path:
            return
            
        encoded_data = {
            "root_folder_name": os.path.basename(self.selected_root),
            "files": []
        }
        
        for file_path in file_list:
            try:
                # Retain structural data relative to parent of the root directory
                rel_path = os.path.relpath(file_path, os.path.dirname(self.selected_root))
                
                with open(file_path, "rb") as f:
                    content = f.read()
                    base64_content = base64.b64encode(content).decode('utf-8')
                    
                encoded_data["files"].append({
                    "rel_path": rel_path,
                    "content": base64_content
                })
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to read {file_path}: {str(e)}")
                return

        try:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(encoded_data, f, indent=4)
            QMessageBox.information(self, "Success", f"Successfully packed {len(file_list)} files into JSON.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save JSON file: {str(e)}")

    def decode_from_json(self):
        """ Reads the backup file, prompts for a target path, and unpacks files cleanly. """
        json_path, _ = QFileDialog.getOpenFileName(self, "Open Encoded JSON File", "", "JSON Files (*.json)")
        if not json_path:
            return
            
        output_dir = QFileDialog.getExistingDirectory(self, "Select Destination Directory to Restore Files")
        if not output_dir:
            return
            
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            if "files" not in data:
                QMessageBox.critical(self, "Error", "Invalid layout format inside JSON file.")
                return
                
            restored_count = 0
            for file_entry in data["files"]:
                rel_path = file_entry["rel_path"]
                content_b64 = file_entry["content"]
                
                # Combine output directory with historical relative structure
                dest_path = os.path.join(output_dir, rel_path)
                
                # Enforce directory layers exist sequentially on the host disk
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                
                # Decode string data directly back to binary chunks
                file_bytes = base64.b64decode(content_b64.encode('utf-8'))
                with open(dest_path, "wb") as f_out:
                    f_out.write(file_bytes)
                restored_count += 1
                
            QMessageBox.information(self, "Success", f"Successfully restored {restored_count} files to {output_dir}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to restore files: {str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BackupApp()
    window.show()
    sys.exit(app.exec())
