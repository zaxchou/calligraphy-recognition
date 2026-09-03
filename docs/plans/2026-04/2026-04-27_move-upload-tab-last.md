---
name: move-upload-tab-last
overview: 将作品上传tab移到最后一个位置
todos:
  - id: move-upload-tab
    content: 将作品上传tab移到最后并更新VALID_TABS和副标题
    status: completed
---

将管理后台"作品上传"tab从第一个位置移到最后一个（作者信息之后）

## 修改文件

`frontend/src/views/ContentVerify.vue` 三处修改：

1. 模板：将"作品上传" el-tab-pane（第48-63行）移到"作者信息" tab-pane 之后
2. VALID_TABS 数组：'upload' 从首位移到末尾
3. 副标题："作品上传"从最前面移到最后面