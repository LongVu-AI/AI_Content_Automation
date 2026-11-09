"""Canonical v2 wire contract. Its copy in Long's app must remain byte-identical."""
import re
import unicodedata
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

CLOSING_LINE = "Sản phẩm có ngay trên TikTok Shop, bấm vào giỏ hàng bên dưới góc trái màn hình để tham khảo sản phẩm bên chúng tôi nhé!"


class Wire(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AssetInfo(Wire):
    id: str
    filename: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size: int = Field(gt=0)
    media_type: Literal["image/png", "image/jpeg", "image/webp"]


class ProductInfo(Wire):
    name: str = Field(min_length=1)
    uses: str = Field(min_length=1)
    price: str = Field(min_length=1)
    product_link: str = Field(min_length=1)
    images: list[AssetInfo] = Field(min_length=1, max_length=1)


class CharacterInfo(Wire):
    id: str = Field(pattern=r"^NV[1-9][0-9]*$")
    name: str
    age: int = Field(ge=18)
    gender: Literal["female", "male"]
    voice: str
    setting: str
    outfit: str
    consistency_block: str
    image: AssetInfo
    audio_mode: Literal["speaking", "voiceover"]


class Scene(Wire):
    id: Literal["1", "2", "3", "3A", "3B", "4"]
    order: int = Field(ge=1, le=5)
    duration_seconds: Literal[8] = 8
    part: str
    action_vi: str = Field(min_length=1)
    dialogue_vi: str = Field(min_length=1)
    prompt_en: str = Field(min_length=50)
    overlay_text: str = ""


class PublishingInfo(Wire):
    slogans: list[str] = Field(min_length=5, max_length=5)
    captions: list[str] = Field(min_length=3, max_length=3)
    selected_caption: int = Field(ge=0, le=2)
    hashtags: list[str] = Field(min_length=8, max_length=10)
    pinned_comment: str
    bgm_note: str = "Chỉ thêm một bản nhạc nền khi dựng, âm lượng nhỏ hơn giọng nói."


class QCInfo(Wire):
    qc_score: float = Field(ge=8, le=10)
    passed: Literal[True] = True
    feedback: str
    warnings: list[str]
    rules_version: Literal["bao-7steps-v2"] = "bao-7steps-v2"


class HandoffV2(Wire):
    schema_version: Literal["2.0"] = "2.0"
    request_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,100}$")
    revision: int = Field(ge=1)
    status: Literal["success"] = "success"
    product: ProductInfo
    character: CharacterInfo
    scenes: list[Scene] = Field(min_length=4, max_length=5)
    publishing: PublishingInfo
    qc: QCInfo
    metadata: dict

    @model_validator(mode="after")
    def content_rules(self):
        ids = [s.id for s in self.scenes]
        if ids not in (["1", "2", "3", "4"], ["1", "2", "3A", "3B", "4"]):
            raise ValueError("Sai thứ tự cảnh.")
        if [s.order for s in self.scenes] != list(range(1, len(self.scenes) + 1)):
            raise ValueError("Sai thứ tự đánh số cảnh.")
        if self.scenes[-1].dialogue_vi != CLOSING_LINE:
            raise ValueError("Câu cuối phải giữ nguyên.")
        for scene in self.scenes:
            for value in (scene.dialogue_vi, scene.prompt_en):
                if re.search(r"https?://|www\.", value, re.I):
                    raise ValueError(f"Cảnh {scene.id} chứa link.")
                price = self.product.price.strip()
                if re.search(r"(?<!\w)" + re.escape(price) + r"(?!\w)", value, re.I):
                    raise ValueError(f"Cảnh {scene.id} chứa giá.")
            if self.character.audio_mode == "speaking" and f'(b) "{scene.dialogue_vi}"' not in scene.prompt_en:
                raise ValueError("Prompt phải giữ nguyên lời thoại.")
            if self.character.audio_mode == "voiceover" and '(b) "' in scene.prompt_en:
                raise ValueError("Bản thuyết minh không chứa lời thoại trong prompt video.")
        pub = self.publishing
        if any(len(t) > 150 or not t.endswith("Bấm giỏ hàng nhé!") for t in pub.captions):
            raise ValueError("Caption tối đa 150 ký tự và kết thúc bằng Bấm giỏ hàng nhé!")
        if any(len(t.split()) > 10 for t in pub.slogans):
            raise ValueError("Slogan tối đa 10 từ.")
        if len(set(t.lower() for t in pub.hashtags)) != len(pub.hashtags):
            raise ValueError("Hashtag bị trùng.")
        for tag in pub.hashtags:
            if not re.fullmatch(r"#[A-Za-z0-9_]+", tag) or unicodedata.normalize("NFD", tag) != tag:
                raise ValueError("Hashtag phải viết liền không dấu.")
        if self.product.product_link not in pub.pinned_comment:
            raise ValueError("Bình luận ghim phải giữ nguyên link.")
        if self.scenes[-1].overlay_text != self.product.price:
            raise ValueError("Chữ giá cảnh cuối phải giữ nguyên.")
        return self
