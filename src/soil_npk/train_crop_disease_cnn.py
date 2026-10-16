"""Train a validated MobileNetV3 crop-disease candidate from PlantVillage folders.

This command is intentionally separate from the lightweight image-similarity
baseline.  It creates a candidate ONNX file plus metadata; it never replaces
the farmer-facing model by default.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path


def _imports():
    try:
        import torch
        from torch import nn
        from torch.utils.data import DataLoader
        from torchvision import datasets, models, transforms
    except ImportError as error:
        raise RuntimeError(
            "CNN training packages are missing. Run: .\\.venv\\Scripts\\python.exe -m pip install -r requirements-training.txt"
        ) from error
    return torch, nn, DataLoader, datasets, models, transforms


def _split_dir(dataset_dir: Path, name: str) -> Path:
    candidates = (name, name.lower(), name.capitalize(), name.upper())
    for candidate in candidates:
        path = dataset_dir / candidate
        if path.is_dir():
            return path
    raise FileNotFoundError(f"Missing {name} folder under {dataset_dir}")


def _accuracy(model, loader, device, torch) -> float:
    model.eval()
    correct = total = 0
    with torch.no_grad():
        for images, labels in loader:
            logits = model(images.to(device))
            correct += int((logits.argmax(dim=1).cpu() == labels).sum())
            total += len(labels)
    return correct / max(total, 1)


def train_candidate(
    dataset_dir: Path,
    model_path: Path,
    epochs: int,
    batch_size: int,
    image_size: int,
    device_name: str,
) -> dict[str, object]:
    torch, nn, DataLoader, datasets, models, transforms = _imports()
    train_dir = _split_dir(dataset_dir, "train")
    validation_dir = _split_dir(dataset_dir, "val")
    test_dir = _split_dir(dataset_dir, "test")
    device = torch.device("cuda" if device_name == "auto" and torch.cuda.is_available() else "cpu" if device_name == "auto" else device_name)
    if device.type == "cuda":
        torch.backends.cudnn.benchmark = True

    normalize = transforms.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225))
    train_transform = transforms.Compose([
        transforms.Resize((image_size, image_size)), transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(12), transforms.ColorJitter(brightness=.12, contrast=.12, saturation=.1),
        transforms.ToTensor(), normalize,
    ])
    evaluation_transform = transforms.Compose([
        transforms.Resize((image_size, image_size)), transforms.ToTensor(), normalize,
    ])
    training_data = datasets.ImageFolder(train_dir, transform=train_transform)
    validation_data = datasets.ImageFolder(validation_dir, transform=evaluation_transform)
    test_data = datasets.ImageFolder(test_dir, transform=evaluation_transform)
    if training_data.classes != validation_data.classes or training_data.classes != test_data.classes:
        raise ValueError("Train, Val and Test class folders must have the same class names.")

    workers = 0  # reliable on Windows and avoids worker-spawn surprises for student laptops
    train_loader = DataLoader(training_data, batch_size=batch_size, shuffle=True, num_workers=workers, pin_memory=device.type == "cuda")
    validation_loader = DataLoader(validation_data, batch_size=batch_size, shuffle=False, num_workers=workers, pin_memory=device.type == "cuda")
    test_loader = DataLoader(test_data, batch_size=batch_size, shuffle=False, num_workers=workers, pin_memory=device.type == "cuda")

    weights = models.MobileNet_V3_Small_Weights.DEFAULT
    model = models.mobilenet_v3_small(weights=weights)
    for parameter in model.features.parameters():
        parameter.requires_grad = False
    model.classifier[3] = nn.Linear(model.classifier[3].in_features, len(training_data.classes))
    model = model.to(device)
    optimizer = torch.optim.AdamW(model.classifier.parameters(), lr=1e-3, weight_decay=1e-4)
    criterion = nn.CrossEntropyLoss()

    best_state = None
    best_validation = -1.0
    for epoch in range(1, epochs + 1):
        model.train()
        running_loss = seen = 0
        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(images), labels)
            loss.backward()
            optimizer.step()
            running_loss += float(loss.detach()) * len(labels)
            seen += len(labels)
        validation_accuracy = _accuracy(model, validation_loader, device, torch)
        print(f"Epoch {epoch}/{epochs} | train loss: {running_loss / max(seen, 1):.4f} | validation accuracy: {validation_accuracy:.2%}")
        if validation_accuracy > best_validation:
            best_validation = validation_accuracy
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}

    if best_state is None:
        raise RuntimeError("Training produced no candidate model.")
    model.load_state_dict(best_state)
    test_accuracy = _accuracy(model, test_loader, device, torch)
    model = model.cpu().eval()
    model_path.parent.mkdir(parents=True, exist_ok=True)
    # Preserve the best candidate before export so a temporary ONNX tooling
    # issue never discards a completed multi-epoch training run.
    checkpoint_path = model_path.with_suffix(".pth")
    torch.save({"state_dict": model.state_dict(), "classes": training_data.classes, "image_size": image_size}, checkpoint_path)
    sample = torch.zeros(1, 3, image_size, image_size)
    torch.onnx.export(
        model, sample, model_path, input_names=["image"], output_names=["logits"],
        # Current PyTorch exporters target ONNX opset 18 directly; requesting
        # an older opset can trigger an unnecessary conversion warning.
        dynamic_axes={"image": {0: "batch"}, "logits": {0: "batch"}}, opset_version=18,
    )
    metadata_path = model_path.with_suffix(".json")
    metadata = {
        "model_format": "mittimitra-mobilenetv3-small-onnx-v1",
        "created_at": datetime.now(UTC).isoformat(),
        "classes": training_data.classes,
        "image_size": image_size,
        "normalization": {"mean": [0.485, 0.456, 0.406], "std": [0.229, 0.224, 0.225]},
        "train_images": len(training_data), "validation_images": len(validation_data), "test_images": len(test_data),
        "best_validation_accuracy": round(best_validation, 4), "test_accuracy": round(test_accuracy, 4),
        "source": "PlantVillage local dataset; controlled-image benchmark, not a field-validation claim.",
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return {"model_path": str(model_path), "checkpoint_path": str(checkpoint_path), "metadata_path": str(metadata_path), **metadata}


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a MobileNetV3 crop-disease candidate and export ONNX.")
    parser.add_argument("--dataset-dir", type=Path, required=True)
    parser.add_argument("--model-path", type=Path, default=Path("artifacts/crop_disease_candidate.onnx"))
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--image-size", type=int, default=224)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    args = parser.parse_args()
    summary = train_candidate(args.dataset_dir, args.model_path, args.epochs, args.batch_size, args.image_size, args.device)
    print(f"Candidate saved: {summary['model_path']}")
    print(f"Validation accuracy: {summary['best_validation_accuracy']:.2%} | Test accuracy: {summary['test_accuracy']:.2%}")


if __name__ == "__main__":
    main()
