from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Unsloth fine-tuning runner for Lumina")
    parser.add_argument("--base-model", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--max-seq-length", type=int, default=16384)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--per-device-batch-size", type=int, default=1)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--lora-rank", type=int, default=64)
    parser.add_argument("--save-merged-16bit", action="store_true")
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        from unsloth import FastLanguageModel  # pyright: ignore[reportMissingImports]
    except Exception as exc:  # pragma: no cover - environment dependent
        raise SystemExit(
            f"Unsloth is not available in this environment: {exc}. Install requirements_finetune.txt on Linux/WSL2 with CUDA."
        )

    if not dataset_path.exists():
        raise SystemExit(f"Dataset not found: {dataset_path}")

    try:
        from datasets import load_dataset  # pyright: ignore[reportMissingImports]
        from transformers import TrainingArguments  # pyright: ignore[reportMissingImports]
        from trl import SFTTrainer  # pyright: ignore[reportMissingImports]
    except Exception as exc:  # pragma: no cover - environment dependent
        raise SystemExit(f"Training dependencies missing: {exc}. Install requirements_finetune.txt.")

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.base_model,
        max_seq_length=args.max_seq_length,
        dtype=None,
        load_in_4bit=True,
    )
    model = FastLanguageModel.get_peft_model(
        model,
        r=args.lora_rank,
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
        lora_alpha=args.lora_rank * 2,
        lora_dropout=0.0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=3407,
    )

    dataset = load_dataset("json", data_files=str(dataset_path), split="train")  # nosec B615

    def format_example(example: dict) -> dict:
        messages = example.get("messages")
        if isinstance(messages, list) and messages:
            text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
        else:
            text = str(example.get("text", ""))
        return {"text": text}

    dataset = dataset.map(format_example)

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=args.max_seq_length,
        packing=False,
        args=TrainingArguments(
            output_dir=str(output_dir / "trainer-output"),
            per_device_train_batch_size=args.per_device_batch_size,
            gradient_accumulation_steps=args.gradient_accumulation_steps,
            num_train_epochs=args.epochs,
            learning_rate=args.learning_rate,
            logging_steps=1,
            save_strategy="epoch",
            report_to="none",
            bf16=False,
            fp16=True,
        ),
    )
    trainer.train()

    adapters_dir = output_dir / "adapters"
    adapters_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(adapters_dir)
    tokenizer.save_pretrained(adapters_dir)

    merged_dir = output_dir / "merged-16bit"
    if args.save_merged_16bit:
        model.save_pretrained_merged(str(merged_dir), tokenizer, save_method="merged_16bit")

    manifest = {
        "base_model": args.base_model,
        "model_name": args.model_name,
        "dataset": str(dataset_path),
        "adapters_dir": str(adapters_dir),
        "merged_dir": str(merged_dir),
        "save_merged_16bit": args.save_merged_16bit,
    }
    (output_dir / "training_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())