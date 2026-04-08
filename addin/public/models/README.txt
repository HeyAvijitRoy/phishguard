This directory is populated by `scripts/sync-models.ps1`.

The shipped reviewer artifact keeps the trained models under:

- `ml/export/onnx/phish_binary.onnx`
- `ml/export/onnx/phish_intent.onnx`
- `ml/export/onnx/vocab.txt`
- `ml/export/onnx/labels.json`
- `ml/export/onnx/phish_binary_labels.json`

Before running the add-in, execute:

`powershell -ExecutionPolicy Bypass -File .\scripts\sync-models.ps1`
