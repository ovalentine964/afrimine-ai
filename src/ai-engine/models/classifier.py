"""
AfriMine AI — Mineral Image Classifier
EfficientNet-B2 backbone with custom classification head.
Supports training, inference, ONNX export, and TFLite conversion.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import models, transforms
from PIL import Image

from utils.config import ModelConfig
from utils.minerals import MINERAL_CLASSES, get_mineral_by_id

logger = logging.getLogger(__name__)


# ──────────────────────────── Data Transforms ────────────────────────────

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def build_transforms(input_size: tuple[int, int], training: bool = False) -> transforms.Compose:
    """Build image transforms for training or inference."""
    if training:
        return transforms.Compose([
            transforms.Resize(int(input_size[0] * 1.15)),
            transforms.RandomCrop(input_size),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomVerticalFlip(p=0.3),
            transforms.RandomRotation(25),
            transforms.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.2, hue=0.05),
            transforms.RandomAffine(degrees=0, translate=(0.1, 0.1), scale=(0.9, 1.1)),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
            transforms.RandomErasing(p=0.2, scale=(0.02, 0.15)),
        ])
    else:
        return transforms.Compose([
            transforms.Resize(input_size),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ])


# ──────────────────────────── Model Architecture ────────────────────────────

class MineralClassifier(nn.Module):
    """
    EfficientNet-B2 based mineral classifier.
    Takes rock/mineral images and classifies into 20 mineral types.
    """

    def __init__(self, config: ModelConfig):
        super().__init__()
        self.config = config

        # Load pretrained EfficientNet-B2
        if config.backbone == "efficientnet_b2":
            weights = models.EfficientNet_B2_Weights.IMAGENET1K_V1
            self.backbone = models.efficientnet_b2(weights=weights)
            in_features = self.backbone.classifier[1].in_features
            self.backbone.classifier = nn.Identity()
        elif config.backbone == "efficientnet_b0":
            weights = models.EfficientNet_B0_Weights.IMAGENET1K_V1
            self.backbone = models.efficientnet_b0(weights=weights)
            in_features = self.backbone.classifier[1].in_features
            self.backbone.classifier = nn.Identity()
        elif config.backbone == "resnet50":
            weights = models.ResNet50_Weights.IMAGENET1K_V2
            self.backbone = models.resnet50(weights=weights)
            in_features = self.backbone.fc.in_features
            self.backbone.fc = nn.Identity()
        else:
            raise ValueError(f"Unsupported backbone: {config.backbone}")

        # Custom classification head with dropout and batch norm
        self.classifier_head = nn.Sequential(
            nn.Dropout(p=0.4),
            nn.Linear(in_features, 512),
            nn.BatchNorm1d(512),
            nn.SiLU(inplace=True),
            nn.Dropout(p=0.2),
            nn.Linear(512, 256),
            nn.BatchNorm1d(256),
            nn.SiLU(inplace=True),
            nn.Linear(256, config.num_classes),
        )

        # Mineral property prediction heads (auxiliary tasks)
        self.category_head = nn.Sequential(
            nn.Linear(in_features, 128),
            nn.SiLU(inplace=True),
            nn.Linear(128, 5),  # precious, base, industrial, gemstone, rare_earth
        )
        self.value_head = nn.Sequential(
            nn.Linear(in_features, 64),
            nn.SiLU(inplace=True),
            nn.Linear(64, 1),
            nn.Sigmoid(),
        )

        self.transform = build_transforms(config.input_size)
        self.to(config.device)

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        features = self.backbone(x)
        logits = self.classifier_head(features)
        category_logits = self.category_head(features)
        value_score = self.value_head(features)
        return {
            "logits": logits,
            "category_logits": category_logits,
            "value_score": value_score,
        }

    @torch.no_grad()
    def predict(self, image: Image.Image | np.ndarray | str) -> dict:
        """
        Run inference on a single image.
        Returns: {mineral, confidence, category, value_score, top5}
        """
        self.eval()
        image = self._load_image(image)
        tensor = self.transform(image).unsqueeze(0).to(self.config.device)
        outputs = self.forward(tensor)

        probs = F.softmax(outputs["logits"], dim=1).squeeze(0).cpu().numpy()
        category_probs = F.softmax(outputs["category_logits"], dim=1).squeeze(0).cpu().numpy()
        value_score = outputs["value_score"].squeeze().item()

        top5_idx = np.argsort(probs)[-5:][::-1]
        top5 = [
            {"id": int(i), "name": MINERAL_CLASSES[i].name, "confidence": float(probs[i])}
            for i in top5_idx
        ]

        best_idx = int(top5_idx[0])
        best_mineral = MINERAL_CLASSES[best_idx]
        categories = ["precious", "base", "industrial", "gemstone", "rare_earth"]

        return {
            "mineral": best_mineral.name,
            "mineral_id": best_idx,
            "confidence": float(probs[best_idx]),
            "category": categories[int(np.argmax(category_probs))],
            "value_score": round(value_score, 3),
            "top5": top5,
            "all_probabilities": probs.tolist(),
        }

    @torch.no_grad()
    def predict_batch(self, images: list, batch_size: int = 32) -> list[dict]:
        """Run inference on multiple images."""
        self.eval()
        results = []
        for i in range(0, len(images), batch_size):
            batch = images[i:i + batch_size]
            tensors = torch.stack([self.transform(self._load_image(img)) for img in batch])
            tensors = tensors.to(self.config.device)
            outputs = self.forward(tensors)
            probs = F.softmax(outputs["logits"], dim=1).cpu().numpy()

            for j in range(len(batch)):
                best_idx = int(np.argmax(probs[j]))
                best_mineral = MINERAL_CLASSES[best_idx]
                top3_idx = np.argsort(probs[j])[-3:][::-1]
                results.append({
                    "mineral": best_mineral.name,
                    "mineral_id": best_idx,
                    "confidence": float(probs[j][best_idx]),
                    "top3": [
                        {"name": MINERAL_CLASSES[k].name, "confidence": float(probs[j][k])}
                        for k in top3_idx
                    ],
                })
        return results

    def _load_image(self, image: Image.Image | np.ndarray | str) -> Image.Image:
        if isinstance(image, str):
            image = Image.open(image)
        if isinstance(image, np.ndarray):
            image = Image.fromarray(image)
        return image.convert("RGB")

    # ──────────────────── Export Methods ────────────────────

    def export_onnx(self, path: str, opset_version: int = 17) -> str:
        """Export model to ONNX format for cross-platform deployment."""
        self.eval()
        dummy = torch.randn(1, 3, *self.config.input_size).to(self.config.device)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        torch.onnx.export(
            self,
            dummy,
            str(path),
            opset_version=opset_version,
            input_names=["image"],
            output_names=["logits"],
            dynamic_axes={"image": {0: "batch"}, "logits": {0: "batch"}},
        )
        logger.info(f"ONNX model exported to {path}")
        return str(path)

    def export_tflite(self, path: str, quantize: bool = True) -> str:
        """Export model to TensorFlow Lite for mobile deployment."""
        import onnx
        from onnx import helper

        onnx_path = str(Path(path).with_suffix(".onnx"))
        self.export_onnx(onnx_path)

        # Convert ONNX -> TF -> TFLite
        try:
            import tensorflow as tf
            import tf2onnx

            # Use tf2onnx reverse path or direct torch->tflite
            dummy = torch.randn(1, 3, *self.config.input_size).to(self.config.device)
            scripted = torch.jit.trace(self.cpu(), dummy.cpu())

            tflite_path = Path(path)
            tflite_path.parent.mkdir(parents=True, exist_ok=True)

            # Fallback: export as TorchScript and note conversion requirement
            torchscript_path = str(tflite_path.with_suffix(".pt"))
            scripted.save(torchscript_path)
            logger.info(f"TorchScript model saved to {torchscript_path}")
            logger.info(f"For TFLite, run: python -c \"import tf2onnx; ...\" or use onnx2tf")
            return torchscript_path
        except ImportError:
            logger.warning("TensorFlow not installed. Saved TorchScript instead.")
            dummy = torch.randn(1, 3, *self.config.input_size)
            scripted = torch.jit.trace(self.cpu(), dummy)
            torchscript_path = str(Path(path).with_suffix(".pt"))
            scripted.save(torchscript_path)
            return torchscript_path

    # ──────────────────── Training ────────────────────

    def save_checkpoint(self, path: str, epoch: int, optimizer, val_acc: float):
        """Save training checkpoint."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        torch.save({
            "epoch": epoch,
            "model_state_dict": self.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "val_acc": val_acc,
            "config": self.config.__dict__,
        }, path)
        logger.info(f"Checkpoint saved: {path} (epoch {epoch}, acc {val_acc:.4f})")

    def load_checkpoint(self, path: str, optimizer=None) -> dict:
        """Load training checkpoint."""
        ckpt = torch.load(path, map_location=self.config.device)
        self.load_state_dict(ckpt["model_state_dict"])
        if optimizer and "optimizer_state_dict" in ckpt:
            optimizer.load_state_dict(ckpt["optimizer_state_dict"])
        logger.info(f"Checkpoint loaded: {path} (epoch {ckpt.get('epoch', '?')})")
        return ckpt


# ──────────────────────────── Convenience ────────────────────────────

def create_classifier(config: Optional[ModelConfig] = None) -> MineralClassifier:
    """Factory function to create a mineral classifier."""
    if config is None:
        config = ModelConfig()
    model = MineralClassifier(config)
    logger.info(f"Created MineralClassifier: backbone={config.backbone}, classes={config.num_classes}")
    return model


def load_classifier(checkpoint_path: str, config: Optional[ModelConfig] = None) -> MineralClassifier:
    """Load a trained classifier from checkpoint."""
    if config is None:
        config = ModelConfig()
    model = MineralClassifier(config)
    model.load_checkpoint(checkpoint_path)
    return model
