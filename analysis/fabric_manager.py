"""File-Based Fabric Manager"""
from pathlib import Path
from typing import List, Dict, Any
import json
from datetime import datetime

class FabricManager:
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)
        self.index_file = self.base_dir / 'index.json'
        if not self.index_file.exists():
            self._write_index({})

    def _read_index(self) -> Dict[str, Any]:
        if self.index_file.exists():
            return json.loads(self.index_file.read_text())
        return {}

    def _write_index(self, index: Dict[str, Any]):
        self.index_file.write_text(json.dumps(index, indent=2))

    def list_fabrics(self) -> List[Dict[str, Any]]:
        index = self._read_index()
        fabrics = []
        for name, data in index.items():
            fabric_dir = self.base_dir / name
            if fabric_dir.exists():
                fabrics.append({
                    'name': name,
                    'created': data.get('created', ''),
                    'modified': data.get('modified', ''),
                    'dataset_count': len(data.get('datasets', [])),
                })
        return sorted(fabrics, key=lambda x: x['modified'], reverse=True)

    def create_fabric(self, name: str):
        index = self._read_index()
        if name in index:
            raise ValueError(f"Fabric '{name}' already exists")
        fabric_dir = self.base_dir / name
        fabric_dir.mkdir(exist_ok=True)
        now = datetime.now().isoformat()
        index[name] = {'created': now, 'modified': now, 'datasets': []}
        self._write_index(index)

    def delete_fabric(self, name: str):
        index = self._read_index()
        if name not in index:
            raise ValueError(f"Fabric '{name}' not found")
        fabric_dir = self.base_dir / name
        if fabric_dir.exists():
            import shutil
            shutil.rmtree(fabric_dir)
        del index[name]
        self._write_index(index)

    def get_fabric_data(self, name: str) -> Dict[str, Any]:
        index = self._read_index()
        if name not in index:
            return {'datasets': []}
        return index[name]

    def add_dataset(self, fabric_name: str, dataset: Dict[str, Any]):
        index = self._read_index()
        if fabric_name not in index:
            raise ValueError(f"Fabric '{fabric_name}' not found")
        index[fabric_name]['datasets'].append(dataset)
        index[fabric_name]['modified'] = datetime.now().isoformat()
        self._write_index(index)
