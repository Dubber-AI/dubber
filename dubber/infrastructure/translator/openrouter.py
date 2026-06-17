import asyncio
import os
from typing import Any

import httpx
from openai import AsyncOpenAI

from dubber.application.ports.translator import TranslatorProvider
from dubber.application.dto.config import TranslatorConfig
from dubber.domain.entities import Subtitle, SubtitleBlock


class ProviderError(Exception):
    pass

_SYSTEM_PROMPT = (
    "Ты — профессиональный переводчик видеокурсов по IT и data science. "
    "Переводи английские субтитры на русский язык, сохраняя живой, разговорный стиль лектора.\n\n"
    "=== ОБЩИЕ ТРЕБОВАНИЯ ===\n"
    "* Сохраняй смысл и стиль преподавателя.\n"
    "* Переводи КРАТКО — примерно той же длины, что и оригинал, чтобы озвучка помещалась в таймкоды.\n"
    "* Не добавляй комментарии, пояснений, вводных слов ('Итак', 'Значит', 'Смотрите').\n"
    "* Не меняй порядок блоков и не удаляй текст.\n"
    "* Количество выходных блоков должно строго совпадать с количеством входных.\n"
    "* Возвращай только перевод.\n\n"
    "=== СТИЛЕВЫЕ ПРАВИЛА ===\n"
    "* 'You' → 'вы' (формальное обращение к слушателю).\n"
    "* 'Let's / Let us' → 'давайте' (а не 'позвольте нам').\n"
    "* 'We're going to' → 'мы будем' или 'сейчас' (а не 'мы собираемся').\n"
    "* 'gonna / wanna' → переводи как 'будем / хотим' (не сохраняй сокращения).\n"
    "* 'So', 'Now', 'Well', 'Okay' в начале фразы → опускай или заменяй на 'итак', 'так', 'ну' только если без них не звучит естественно.\n"
    "* 'Right?' в конце → 'верно?' или 'так?' (а не 'правильно?').\n\n"
    "=== ПРАВИЛА ПЕРЕВОДА КОДА И КОМАНД ===\n"
    "* Команды терминала, названия файлов, переменных, функций, путей — оставляй на английском.\n"
    "* Фрагменты кода (например, 'def train():') — не переводи, оставляй как есть.\n"
    "* Комментарии в коде — переводи.\n"
    "* Имена собственные (Andrew Ng, Geoffrey Hinton) — оставляй на английском.\n\n"
    "=== ТЕРМИНЫ, КОТОРЫЕ НЕ ПЕРЕВОДЯТСЯ ===\n"
    "Если термин есть в списке ниже — оставляй на английском. "
    "Не переводи дословно и не транслитируй кириллицей.\n\n"
    "Языки и фреймворки:\n"
    "Python, JavaScript, TypeScript, Node.js, Docker, Kubernetes, FastAPI, Django, Flask, "
    "PostgreSQL, Redis, MongoDB, TensorFlow, PyTorch, Keras, Jupyter Notebook, NumPy, Pandas, "
    "Scikit-learn, Matplotlib, Seaborn, OpenCV, Git, GitHub, Linux.\n\n"
    "ML / Deep Learning:\n"
    "CNN, RNN, LSTM, GRU, Transformer, BERT, GPT, GAN, VAE, autoencoder, "
    "backpropagation, gradient descent, activation function, loss function, optimizer, "
    "epoch, batch, minibatch, learning rate, hyperparameter, overfitting, underfitting, "
    "regularization, data augmentation, dropout, batch normalization, "
    "embedding, fine-tuning, pre-training, inference, training, validation, testing, "
    "feature map, pooling, stride, padding, kernel, filter, fully connected layer, "
    "softmax, sigmoid, tanh, ReLU, LeakyReLU, ELU, GELU, Swish, "
    "convolution, deconvolution, transpose convolution, dilated convolution, "
    "transfer learning, curriculum learning, self-supervised learning, "
    "reinforcement learning, supervised learning, unsupervised learning, "
    "zero-shot learning, few-shot learning, domain adaptation, "
    "latent space, latent variable, prior, posterior, likelihood, "
    "KL divergence, JS divergence, adversarial, discriminator, generator, "
    "inception score, FID, perplexity, BLEU, ROUGE, "
    "token, tokenizer, vocabulary, word2vec, GloVe, FastText, BPE, sentencepiece, "
    "self-attention, multi-head attention, position encoding, feed-forward network, "
    "layer normalization, residual connection, skip connection, bottleneck, "
    "depthwise separable convolution, deformable convolution, "
    "ROI pooling, ROI align, NMS, anchor box, anchor, IoU, mAP, AR, AP, "
    "RPN, FPN, SSD, RetinaNet, Mask R-CNN, U-Net, DeepLab, PSPNet, SegNet, FCN, "
    "ResNet, VGG, AlexNet, YOLO, MobileNet, EfficientNet, DenseNet, "
    "ResNeXt, Wide ResNet, SE-Net, CBAM, GhostNet, MixNet, "
    "ShuffleNet, SqueezeNet, NASNet, EfficientDet, CenterNet, FCOS, DETR, "
    "YOLOv3, YOLOv4, YOLOv5, YOLOv8, YOLOv9, YOLOv10, YOLOX, RT-DETR, NanoDet.\n\n"
    "Общие IT-термины:\n"
    "dataset, label, annotation, bounding box, classification, regression, clustering, "
    "segmentation, object detection, face recognition, NLP, computer vision, "
    "deep learning, machine learning, artificial intelligence, neural network, "
    "model, weights, biases, parameters, weights and biases, "
    "deployment, API, REST, JSON, CSV, pixel, image, video, frame, channel, tensor, "
    "matrix, vector, scalar, dot product, gradient, derivative, partial derivative, "
    "chain rule, Jacobian, Hessian, momentum, Adam, RMSprop, AdaGrad, SGD, "
    "learning rate decay, warm-up, checkpoint, early stopping, "
    "accuracy, precision, recall, F1-score, cross-entropy, one-hot encoding, "
    "TP, FP, TN, FN, GPU, CPU, TPU.\n\n"
    "=== ПРИМЕРЫ ПЕРЕВОДА ===\n"
    "Плохо: 'Теперь, давайте посмотрим, что такое backpropagation алгоритм.'\n"
    "Хорошо: 'Сейчас разберём алгоритм backpropagation.'\n\n"
    "Плохо: 'Вы собираетесь использовать Python для этого проекта.'\n"
    "Хорошо: 'Для этого проекта вы будете использовать Python.'\n\n"
    "Плохо: 'Это называется свёрточная нейронная сеть или CNN.'\n"
    "Хорошо: 'Это называется CNN — convolutional neural network.'\n\n"
    "Плохо: 'Позвольте нам запустить train.py.'\n"
    "Хорошо: 'Давайте запустим train.py.'\n\n"
    "Формат ответа: верни JSON-объект с полем 'blocks', содержащим массив строк. "
    "Каждая строка — перевод соответствующего блока."
)


class OpenRouterTranslatorProvider(TranslatorProvider):
    def __init__(self, config: TranslatorConfig) -> None:
        self._config = config
        api_key = os.getenv("OPENROUTER_API_KEY", "")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable is not set")
        self._client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            timeout=config.timeout,
            http_client=httpx.AsyncClient(
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            ),
        )
        self._semaphore = asyncio.Semaphore(5)

    async def healthcheck(self) -> bool:
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False

    async def translate_batch(
        self, blocks: list[SubtitleBlock]
    ) -> list[SubtitleBlock]:
        if not blocks:
            return []

        # Split into sub-batches to avoid exceeding model token limits
        batch_size = self._config.batch_size
        sub_batches = [
            blocks[i : i + batch_size] for i in range(0, len(blocks), batch_size)
        ]

        result: list[SubtitleBlock] = []
        for sub_batch in sub_batches:
            translated = await self._translate_sub_batch_safe(sub_batch)
            result.extend(translated)
        return result

    async def _translate_sub_batch_safe(
        self, blocks: list[SubtitleBlock], _depth: int = 0
    ) -> list[SubtitleBlock]:
        """Translate a sub-batch with adaptive splitting on count mismatch.

        If the model returns fewer blocks than expected, split the batch in half
        and retry each half recursively. Stops splitting at single-block level.
        """
        try:
            return await self._translate_sub_batch(blocks)
        except ProviderError:
            if len(blocks) <= 1:
                raise
            if _depth > 5:
                raise

            mid = len(blocks) // 2
            left = await self._translate_sub_batch_safe(blocks[:mid], _depth + 1)
            right = await self._translate_sub_batch_safe(blocks[mid:], _depth + 1)
            return left + right

    async def _translate_sub_batch(
        self, blocks: list[SubtitleBlock]
    ) -> list[SubtitleBlock]:
        import json

        texts = [self._block_to_text(b) for b in blocks]
        payload = {"blocks": texts}

        response_text = await self._call_with_retry(
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ]
        )
        translated_texts = self._extract_translated(response_text, len(blocks))

        if len(translated_texts) != len(blocks):
            raise ProviderError(
                f"Translated blocks count mismatch: expected {len(blocks)}, got {len(translated_texts)}"
            )

        result: list[SubtitleBlock] = []
        for block, trans_text in zip(blocks, translated_texts, strict=True):
            per_sub_texts = [trans_text]
            if len(per_sub_texts) != len(block.subtitles):
                raise ProviderError(
                    f"Subtitle count mismatch in block: expected {len(block.subtitles)}, got {len(per_sub_texts)}"
                )
            translated_subs = [
                Subtitle(
                    index=sub.index,
                    start=sub.start,
                    end=sub.end,
                    text=sub_text,
                )
                for sub, sub_text in zip(block.subtitles, per_sub_texts, strict=True)
            ]
            result.append(SubtitleBlock(translated_subs))
        return result

    def _block_to_text(self, block: SubtitleBlock) -> str:
        return "\n".join(s.text for s in block.subtitles)

    def _extract_translated(self, response_text: str, expected_count: int) -> list[str]:
        import json
        import re

        # Try to parse JSON from the response
        try:
            data = json.loads(response_text)
            if isinstance(data, dict) and "blocks" in data and isinstance(data["blocks"], list):
                return list(data["blocks"])
        except json.JSONDecodeError:
            pass

        # Fallback: extract quoted strings or lines
        # Try markdown code blocks
        match = re.search(r"```(?:json)?\s*\n(.*?)\n```", response_text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                if isinstance(data, dict) and "blocks" in data and isinstance(data["blocks"], list):
                    return list(data["blocks"])
            except json.JSONDecodeError:
                pass

        # Last resort: split by newlines and take non-empty lines
        lines = [line.strip() for line in response_text.splitlines() if line.strip()]
        if len(lines) >= expected_count:
            return lines

        # If count mismatch, raise so API/provider drift fails fast
        if len(lines) < expected_count:
            raise ProviderError(
                f"translate_batch returned {len(lines)} blocks, expected {expected_count}. "
                f"translated_list length: {len(lines)}, expected misses: {expected_count}"
            )
        return lines

    async def _call_with_retry(self, messages: list[dict[str, Any]]) -> str:
        for attempt in range(self._config.max_retries):
            async with self._semaphore:
                try:
                    response = await self._client.chat.completions.create(
                        model=self._config.model,
                        messages=messages,  # type: ignore[arg-type]
                        temperature=0.3,
                        max_tokens=16384,
                    )
                    content = response.choices[0].message.content or ""
                    return content.strip()
                except Exception as exc:
                    status = getattr(exc, "status_code", None)
                    if status in {429, 500, 502, 503, 504}:
                        delay = self._config.base_delay * (2 ** attempt)
                        await asyncio.sleep(delay)
                        continue
                    if attempt == self._config.max_retries - 1:
                        raise
                    await asyncio.sleep(self._config.base_delay)
        raise RuntimeError("Max retries exceeded for translation")
