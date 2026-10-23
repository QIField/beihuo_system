/* -*- coding:utf-8 -*-
 * 个人记事本页面逻辑
 * 列表加载 / 新增 / 编辑 / 删除 / 关键字搜索
 * 所有动态内容均通过 text() 插入，避免 HTML 注入
 */
layui.use(['layer', 'jquery'], function () {
    var layer = layui.layer;
    var $ = layui.jquery;

    var SUMMARY_LEN = 80;
    var editingId = null;   // null=新增，数字=编辑
    var layerIndex = null;
    var notesCache = [];    // 最近一次列表数据，编辑回填用

    // ================= 列表 =================

    function loadNotes() {
        var keyword = $.trim($('#keyword').val());
        $.ajax({
            url: '/new/api/notepad/list',
            type: 'GET',
            data: keyword ? { keyword: keyword } : {},
            dataType: 'json',
            success: function (res) {
                if (res.code === 200) {
                    notesCache = res.data || [];
                    renderNotes(notesCache);
                } else {
                    layer.msg(res.msg || '获取列表失败', { icon: 2 });
                }
            },
            error: function () {
                layer.msg('网络异常，获取列表失败', { icon: 2 });
            }
        });
    }

    function displayTitle(note) {
        if (note.title) return note.title;
        var firstLine = String(note.content || '').split('\n')[0];
        return truncate(firstLine, SUMMARY_LEN) || '（无标题）';
    }

    function displaySummary(note) {
        var content = String(note.content || '');
        if (!note.title) {
            // 无标题时首行已作为标题展示，摘要从第二行开始
            var lines = content.split('\n');
            content = lines.slice(1).join('\n');
        }
        return truncate(content, SUMMARY_LEN);
    }

    function truncate(text, maxLen) {
        text = String(text || '');
        return text.length > maxLen ? text.slice(0, maxLen) + '…' : text;
    }

    function renderNotes(list) {
        var $body = $('#noteBody').empty();
        if (!list.length) {
            var emptyText = $.trim($('#keyword').val()) ? '无匹配笔记' : '暂无笔记，点击右上角「新增笔记」开始记录';
            $body.append($('<tr>').append(
                $('<td colspan="4" class="np-empty">').text(emptyText)
            ));
            return;
        }
        $.each(list, function (i, note) {
            $body.append(
                $('<tr>').append(
                    $('<td>').append(
                        $('<div class="np-note-title">').text(displayTitle(note)),
                        $('<div class="np-note-summary">').text(displaySummary(note))
                    ),
                    $('<td>').text(note.created_time || '-'),
                    $('<td>').text(note.updated_time || '-'),
                    $('<td class="np-op">').append(
                        $('<a data-act="edit">').attr('data-id', note.id).text('编辑'),
                        $('<a data-act="del" class="np-del">').attr('data-id', note.id).text('删除')
                    )
                )
            );
        });
    }

    // ================= 新增 / 编辑弹层 =================

    function openModal(note) {
        editingId = note ? note.id : null;
        $('#noteTitle').val(note ? (note.title || '') : '');
        $('#noteContent').val(note ? (note.content || '') : '');
        updateCounter();
        layerIndex = layer.open({
            type: 1,
            title: note ? '编辑笔记' : '新增笔记',
            area: ['560px', 'auto'],
            maxmin: false,
            content: $('#noteModal'),
            cancel: function () { layerIndex = null; }
        });
    }

    function closeModal() {
        if (layerIndex !== null) {
            layer.close(layerIndex);
            layerIndex = null;
        }
    }

    function updateCounter() {
        $('#contentCount').text($('#noteContent').val().length);
    }

    function saveNote() {
        var payload = {
            title: $.trim($('#noteTitle').val()),
            content: $.trim($('#noteContent').val())
        };
        if (!payload.content) {
            layer.msg('笔记内容不能为空', { icon: 2 });
            return;
        }
        var url = editingId === null ? '/new/api/notepad/create' : '/new/api/notepad/update';
        if (editingId !== null) payload.id = editingId;
        $.ajax({
            url: url,
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(payload),
            dataType: 'json',
            success: function (res) {
                if (res.code === 200) {
                    layer.msg(res.msg || '保存成功', { icon: 1 });
                    closeModal();
                    loadNotes();
                } else {
                    layer.msg(res.msg || '保存失败', { icon: 2 });
                }
            },
            error: function (xhr) {
                var msg = '网络异常，保存失败';
                try { msg = JSON.parse(xhr.responseText).msg || msg; } catch (e) { }
                layer.msg(msg, { icon: 2 });
            }
        });
    }

    // ================= 删除 =================

    function deleteNote(noteId) {
        layer.confirm('确定删除这条笔记吗？删除后不可恢复。', { icon: 3, title: '删除确认' }, function (index) {
            layer.close(index);
            $.ajax({
                url: '/new/api/notepad/delete',
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({ id: noteId }),
                dataType: 'json',
                success: function (res) {
                    if (res.code === 200) {
                        layer.msg('删除成功', { icon: 1 });
                        loadNotes();
                    } else {
                        layer.msg(res.msg || '删除失败', { icon: 2 });
                    }
                },
                error: function (xhr) {
                    var msg = '网络异常，删除失败';
                    try { msg = JSON.parse(xhr.responseText).msg || msg; } catch (e) { }
                    layer.msg(msg, { icon: 2 });
                }
            });
        });
    }

    // ================= 事件绑定 =================

    $('#btnAdd').on('click', function () { openModal(null); });

    $('#btnSearch').on('click', loadNotes);

    $('#keyword').on('keydown', function (e) {
        if (e.key === 'Enter') loadNotes();
    });

    // 列表操作（事件委托，一次绑定全局生效）
    $('#noteBody').on('click', 'a[data-act]', function () {
        var noteId = $(this).attr('data-id');
        if ($(this).attr('data-act') === 'del') {
            deleteNote(noteId);
            return;
        }
        var note = null;
        $.each(notesCache, function (i, n) {
            if (String(n.id) === String(noteId)) { note = n; return false; }
        });
        if (note) openModal(note);
    });

    $('#noteContent').on('input', updateCounter);

    $('#btnSave').on('click', saveNote);

    $('#btnCancel').on('click', closeModal);

    // ================= 初始化 =================

    loadNotes();
});
