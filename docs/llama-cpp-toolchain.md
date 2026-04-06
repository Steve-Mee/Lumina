# llama.cpp Toolchain For Lumina

## Doel

Deze toolchain maakt het mogelijk om een door Unsloth gefinetunede Hugging Face checkpoint naar GGUF te exporteren en daarna als lokaal model in Ollama te registreren.

## Wat is toegevoegd

- `scripts/setup_llama_cpp.py`: clone/update en build van `llama.cpp` op Linux of WSL2.
- Launcher adminpaneel: knoppen voor toolchain setup, GGUF export en `ollama create` registratie.
- Die launcherknoppen worden automatisch uitgeschakeld buiten Linux of WSL2 of wanneer de vereiste outputbestanden nog ontbreken.
- `ModelTrainer.inspect_llama_cpp_toolchain()`: runtime-inspectie van converter-, quantize- en setupstatus.

## Verwacht platform

- Linux native of WSL2
- `git`
- `cmake`
- CUDA-capabele NVIDIA omgeving voor de bredere fine-tune workflow

## Installatie

1. Activeer de Lumina Python omgeving.
2. Voer `python scripts/setup_llama_cpp.py` uit.
3. Controleer dat `tools/llama.cpp/convert_hf_to_gguf.py` bestaat.
4. Controleer dat `tools/llama.cpp/build/bin/llama-quantize` bestaat na de build.

## Volledige flow

1. Train adapters of merged model via Unsloth.
2. Exporteer merged output naar GGUF met het commando dat de launcher toont.
3. Gebruik het gegenereerde `Modelfile` in `state/unsloth-output/Modelfile`.
4. Registreer het model met `ollama create`.
5. Zet daarna in de launcher het nieuwe model als runtime-upgrade.

## Statusbestanden

- `state/llama_cpp_setup.json`: laatste setup-uitkomst van het toolchainscript.
- `state/training_pipeline_status.json`: laatste trainingsomgeving-inspectie.

## Wat nog niet automatisch gebeurt

- Er is nog geen automatische download van een CUDA toolchain.
- Er is nog geen automatische verificatie dat de geëxporteerde GGUF functioneel correcte outputs geeft voor Lumina-prompts.
- Er is nog geen automatische promotie van een nieuw model naar alle klanten; dat blijft gestuurd door `lumina_model_catalog.json` en releasebeleid.