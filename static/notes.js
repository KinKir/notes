'use strict';

_.mixin({
  im : function (o, selector) {
    var pre_arguments = _.rest(arguments, 2);
    return function () {
      var method = typeof selector == "function" ? selector : o[selector];
      if (method === void 0) {
        throw new TypeError("Object " + o + " has no method '" + selector + "'");
      } else {
        return method.apply(o, pre_arguments.concat(_.toArray(arguments)));
      }
    };
  }
});

/// other stuff

function getCookie(name) {
  var r = document.cookie.match("\\b" + name + "=([^;]*)\\b");
  return r ? r[1] : undefined;
}

var months = {
  0 : "Jan", 1 : "Feb", 2 : "Mar", 3 : "Apr", 4 : "May", 5 : "Jun",
  6 : "Jul", 7 : "Aug", 8 : "Sep", 9 : "Oct", 10 : "Nov", 11 : "Dec"
};
var days = {
  0 : "Sun", 1 : "Mon", 2 : "Tue", 3 : "Wed", 4 : "Thu", 5 : "Fri", 6 : "Sat"
};

// Converts a date object into a short time string
function pad2(n) {
  var o = "0" + n;
  return o.substring(o.length-2);
}

function shortTime(date, showTime, forceFull) {
  var now = new Date();
  var h = date.getHours();
  var hs = h%12 == 0 ? 12 : h%12;
  var ampm = h < 12 ? "am" : "pm";
  var time = hs + ":" + pad2(date.getMinutes()) + " " + ampm;
  var cptime = showTime ? " " + time : "";
  if (!forceFull && date.getFullYear()  == now.getFullYear()) {
    if (date.getMonth() == now.getMonth()
        && (date.getDate() == now.getDate()
            || (date.getDate() + 1 == now.getDate()
                && now.getHours() < 12
                && date.getHours() + date.getMinutes()/60 > 12))) {
      return time;
    } else {
      return days[date.getDay()] + ' ' + months[date.getMonth()] + ' ' + date.getDate() + cptime;
    }
  } else {
    return days[date.getDay()] + ' ' + (date.getMonth() + 1) + "/" + pad2(date.getDate()) + "/" + pad2(date.getFullYear() % 100) + cptime;
  }
};

// Converts a filesize (in bytes) to a sensible size description
function sensibleSize(size) {
  size = parseInt(size);
  var sensibleSize;
  if (size < 1024/10) {
    sensibleSize = size + " B";
  } else if (size < 1024*1024/10) {
    sensibleSize = (size/1024).toPrecision(2) + " kB";
  } else {
    sensibleSize = (size/1024/1024).toPrecision(2) + " MB";
  }
};


$(function () {
  $('.timestamp').each(function () {
    var $this = $(this);
    $this.text(shortTime(new Date(+$this.text()*1000), true, $this.hasClass("timestamp-full")));
  });
});

function generateGUID() {
  return (_.now().toString(36)
          + "-" + Math.random().toString(16).slice(2)
          + "-" + Math.random().toString(16).slice(2));
}

function addInlineAttachment(cm) {

  var $notifier = $('<div class="notifier">').appendTo(document.body);

  $notifier.text("Uploading...").hide();
  var _notifierTimeout = null;
  function notifierTimeout(f, time) {
    if (_notifierTimeout) {
      window.clearTimeout(_notifierTimeout);
    }
    _notifierTimeout = window.setTimeout(f, time);
  }

  // extracted from inline-attachment.js

  var settings = {
    imageTypes: [
      'image/jpeg',
      'image/png',
      'image/jpg',
      'image/gif'
    ],
    ignoredTypes: [
      'text/plain'
    ]
  };

  function isFileAllowed(file) {
    return settings.ignoredTypes.indexOf(file.type) === -1;
  }

  function uploadFile(file) {
    var formData = new FormData(),
        xhr = new XMLHttpRequest();

    var filename = generateGUID();
    var linkname = filename;
    if (file.name) {
      linkname += '/' + file.name;
    }

    $('#xsrf_data input').each(function () {
      formData.append(this.name, this.value);
    });

    formData.append('file', file, file.name || filename);

    var uploadurl = "/wiki/" + $('#wikiname').val() + '/file/u/' + linkname;
    console.log(uploadurl);
    console.log(formData);

    insert(file, linkname, file.name);
    notifierTimeout(function () {
      $notifier.show().text("Uploading " + linkname);
    }, 0);

    xhr.open('POST', uploadurl, true);
    xhr.onload = function () {
      if (xhr.readyState === 4) {
      if (xhr.status == 200 || xhr.status === 201) { // OK or Created
        notifierTimeout(function () {
          $notifier.show().text("Uploaded " + linkname);
          notifierTimeout(function () {
            $notifier.hide();
          }, 2000);
        }, 0);
        console.log('success');
      } else {
        notifierTimeout(function () {
          $notifier.show().text("Failed to upload " + linkname);
          notifierTimeout(function () {
            $notifier.hide();
          }, 5000);
        }, 0);
        console.log('failure');
      }
      }
    };
    xhr.onerror = function (e) {
      notifierTimeout(function () {
        $notifier.show().text("Failed to upload " + linkname);
        notifierTimeout(function () {
          $notifier.hide();
        }, 5000);
      }, 0);
      console.log('failure');
    };
    xhr.upload.onprogress = function (e) {
      notifierTimeout(function () {
        var perc = 100 * e.loaded / Math.max(e.loaded, e.total);
        $notifier.show().text("Uploading " + linkname + ": " + perc.toFixed(1) + "%");
      }, 0);
    };
    xhr.send(formData);
  }

  function insert(file, linkname, filename) {
    var link = '[' + (filename || '') + '](uuid:' + linkname + ')';
    if (settings.imageTypes.indexOf(file.type) >= 0) {
      link = '!' + link;
    }
    cm.replaceSelection(link);
  }

  function onPaste(e) {
    var result = false,
        clipboardData = e.clipboardData,
        items;
    if (typeof clipboardData === "object") {
      items = clipboardData.items || clipboardData.files || [];
      for (var i = 0; i < items.length; i++) {
        var item = items[i];
        var file = item.getAsFile();
        if (file && isFileAllowed(item)) {
          result = true;
          uploadFile(file);
        }
      }
    }
    if (result) { e.preventDefault(); }
    return result;
  }

  function onDrop(e) {
    var result = false;
    for (var i = 0; i < e.dataTransfer.files.length; i++) {
      var file = e.dataTransfer.files[i];
      console.log(file);
      if (file && isFileAllowed(file)) {
        result = true;
        uploadFile(file);
      }
    }
    return result;
  }

  var $el = $(cm.getWrapperElement());
  cm.getWrapperElement().addEventListener("paste", function (e) {
    console.log("paste");
    onPaste(e);
  }, false);
  cm.on("drop", function (data, e) {
    if (onDrop(e)) {
      e.stopPropagation();
      e.preventDefault();
      return true;
    } else {
      return false;
    }
  });
}

// drafts are in localStorage of with keys wikiname/{new,edit}/randomstring[/docid]
function wikiPathName() {
  var path = location.pathname.split("/");
  return path.slice(path.indexOf("wiki")+1);
}
function getDrafts() {
  var wiki = wikiPathName()[0];
  var drafts = [];
  for (var i = 0; i < localStorage.length; i++) {
    var k = localStorage.key(i);
    if (k.startsWith(wiki)) {
      drafts.push(k);
    }
  }
  return drafts;
}
function constructDraftKey() {
  var path = wikiPathName();
  var wname = path[0],
      docid = 2 < path.length ? path[2] : null;
  if (docid == null) {
    return wname + "/new/" + getDraftCode();
  } else {
    return wname + "/edit/" + getDraftCode() + "/" + docid;
  }
}
function makeDraftsList() {
  var $drafts = $("#drafts_list").empty();
  if ($drafts.length == 0) {
    $drafts = $('<div id="drafts_list" class="sidebox">').appendTo($("#sidebar"));
  }
  $drafts.append('Drafts:').append($('<br>'));
  var ds = getDrafts();
  $drafts.toggle(ds.length > 0);
  var $list = $('<ul>').appendTo($drafts);
  for (var i = 0; i < ds.length; i++) {
    var key = ds[i].split("/");
    var data = JSON.parse(localStorage.getItem(ds[i]));
    var $li = $('<li>').appendTo($list);
    var $a = $('<a>').appendTo($li);
    if (key[1] === "new") {
      $a.attr("href", '/wiki/' + key[0] + '/edit?localdraft=' + key[2]);
      $a.text("new (" + shortTime(new Date(data.edited)) +")");
    } else if (key[1] === "edit") {
      $a.attr("href", '/wiki/' + key[0] + '/edit/' + key[3] + '?localdraft=' + key[2]);
      $a.text("doc " + key[3] + " (" + shortTime(new Date(data.edited)) +")");
    }
    $a.attr("title", data.content.slice(0, 50) + "...");
  }
}

function queryParameter(key, def) {
  if (arguments.length === 1) {
    def = null;
  }
  var parts = window.location.search.slice(1).split("&");
  for (var i = 0; i < parts.length; i++) {
    var kv = parts[i].split("=");
    if (decodeURIComponent(kv[0]) === key) {
      return decodeURIComponent(kv[1]);
    }
  }
  return def;
}
function addQueryParameter(key, val) {
  return window.location.href + (window.location.search ? "&" : "?") + encodeURIComponent(key) + "=" + encodeURIComponent(val);
}

var curr_draft_code = null;
function getDraftCode() {
  if (curr_draft_code === null) {
    var code = queryParameter("localdraft", null);
    if (code) {
      curr_draft_code = code;
    }
  }
  if (curr_draft_code === null) {
    curr_draft_code = generateGUID();
    window.history.replaceState(null, document.title, addQueryParameter("localdraft", curr_draft_code));
  }
  return curr_draft_code;
}
function saveDraft(contents) {
  var code = getDraftCode();
  var key = constructDraftKey();
  localStorage.setItem(key, JSON.stringify({
    content : contents,
    edited : new Date().getTime()
  }));

  makeDraftsList();
}
function getDraft() {
  var key = constructDraftKey();
  try {
    return JSON.parse(localStorage.getItem(key)).content;
  } catch (x) {
    return null;
  }
}
function discardDraft() {
  localStorage.removeItem(constructDraftKey());
}

var current_official_contents = null;

$(function () {
  makeDraftsList();

  if (document.getElementById('edit')) {

    current_official_contents = $('#edit textarea').val();

    var draft = getDraft();
    if (draft !== null) {
      $('#edit textarea').val(draft);
    }

    var cm = CodeMirror.fromTextArea($('#edit textarea')[0], {
      mode: 'markdown-math',
      indentWithTabs: false,
      tabSize: 4,
      lineWrapping: true,
      lineNumbers: true,
      viewportMargin: Infinity,
      extraKeys: {
        "Enter": "newlineAndIndentContinueMarkdownList",
        'Ctrl-S': function (cm) {
          var $form = $(document.getElementById('edit'));
          $form.submit();
        }
      }
    });

    addInlineAttachment(cm);

    if ($('#edit textarea').attr('codemirror-focus-end') === "true") {
      cm.execCommand('goDocEnd');
    }
    cm.focus();

    $('#edit').on("submit", function () {
      cm.markClean();
    });

    cm.on("change", _.debounce(function (cm) {
      saveDraft(cm.getValue());
    }, 500));

    $("#edit_cancel_button").on("click", function (e) {
      if (cm.getValue() !== current_official_contents) {
        if (!confirm("There are unsaved changes. Discard draft?")) {
          e.preventDefault();
          return;
        }
      }
      discardDraft();
      cm.markClean();
    });

    $(window).on('beforeunload', function () {
      if (!cm.isClean()) {
        saveDraft(cm.getValue());
        //return "There are unsaved changes.";
      }
    });
  }
});