# Kling Omni Video API Specification

Base URL: `https://api-beijing.klingai.com`

## Create Task

**POST** `/v1/videos/omni-video`

### Authentication

JWT Bearer token (HS256). Claims: `iss` = access_key, `exp` = now + 1800, `nbf` = now - 5.

### Request Body

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `model_name` | string | optional | `kling-video-o1` | `kling-video-o1` or `kling-v3-omni` |
| `prompt` | string | conditional | — | Text prompt, max 2500 chars. Use `<<<image_N>>>`, `<<<element_N>>>`, `<<<video_1>>>` to reference inputs |
| `image_list` | array | optional | — | Reference images, first/end frames. Up to 7 without video, up to 4 with video |
| `element_list` | array | optional | — | Subject references from element library (element_id) |
| `video_list` | array | optional | — | Reference video for editing or style transfer |
| `mode` | string | optional | `pro` | `std` (standard 720p) or `pro` (high quality 1080p) |
| `duration` | string | optional | `5` | Video length: `3`-`15` seconds |
| `aspect_ratio` | string | conditional | — | `16:9`, `9:16`, `1:1`. Required when no first_frame or video editing |
| `sound` | string | optional | `off` | `on` or `off`. Audio generation. Cannot use with reference video |
| `multi_shot` | boolean | optional | false | Multi-shot mode |
| `shot_type` | string | conditional | — | `customize` or `intelligence`. Required when multi_shot=true |
| `multi_prompt` | array | optional | — | Per-shot prompts: `[{index, prompt, duration}]`. Max 6 shots |
| `callback_url` | string | optional | — | Webhook URL for task status changes |
| `external_task_id` | string | optional | — | Custom task ID (must be unique per user) |

### image_list Structure

```json
"image_list": [
  {"image_url": "base64_or_url", "type": "first_frame"},
  {"image_url": "base64_or_url", "type": "end_frame"},
  {"image_url": "base64_or_url"}
]
```

**CRITICAL**: The `type` field is ONLY for `first_frame` and `end_frame`. For reference images, **do NOT set the `type` field**. The docs explicitly state: "如图片非首帧或尾帧，请勿配置 type 参数"

**Token mapping**: Images are referenced in the prompt by position in `image_list`:
- `image_list[0]` → `<<<image_1>>>`
- `image_list[1]` → `<<<image_2>>>`
- `image_list[2]` → `<<<image_3>>>`
- etc.

**Image requirements**:
- Formats: .jpg / .jpeg / .png
- Size: ≤ 10MB
- Dimensions: width and height ≥ 300px, aspect ratio 1:2.5 ~ 2.5:1
- Can be base64 encoded or URL

### video_list Structure

```json
"video_list": [
  {"video_url": "url", "refer_type": "base", "keep_original_sound": "yes"}
]
```

- `refer_type`: `base` (video editing) or `feature` (style/camera reference)
- `keep_original_sound`: `yes` or `no`
- When video_list is present, `sound` must be `off`
- Max 1 video, ≤ 200MB, 3-10s, MP4/MOV, 720-2160px, 24-60fps

### Prompt Tips (from docs)

- Use `<<<image_N>>>` to reference images by position in image_list
- Use `<<<element_N>>>` to reference elements by position in element_list
- Use `<<<video_1>>>` to reference the video
- For audio (sound=on): Put dialogue in quotation marks, describe ambient sounds explicitly
- Be specific about character appearance, clothing, actions

## Query Task

**GET** `/v1/videos/omni-video/{task_id}`

### Response (200)

```json
{
  "code": 0,
  "message": "string",
  "request_id": "string",
  "data": {
    "task_id": "string",
    "task_status": "submitted|processing|succeed|failed",
    "task_status_msg": "string",
    "task_result": {
      "videos": [{
        "id": "string",
        "url": "string",
        "watermark_url": "string",
        "duration": "string"
      }]
    },
    "created_at": 1722769557708,
    "updated_at": 1722769557708
  }
}
```

**Note**: Generated video URLs expire after 30 days — download immediately.

## Duration Rules

| Scenario | Duration Support |
|---|---|
| Text-to-video, image-to-video (no first/end frame) | 3-10s |
| Video editing (refer_type=base) | Matches input video length |
| Other (images+elements, or video refer_type=feature) | 3-10s |

## Video Extension

Use video reference with prompt "基于<<<video_1>>>，生成下一个镜头" (generate next shot based on video_1):

```json
{
  "prompt": "基于<<<video_1>>>，生成下一个镜头",
  "video_list": [{"video_url": "xxx", "refer_type": "feature", "keep_original_sound": "yes"}],
  "mode": "pro"
}
```
