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

$(function () {
  if (document.getElementById('edit')) {
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
    if ($('#edit textarea').attr('codemirror-focus-end') === "true") {
      cm.execCommand('goDocEnd');
    }
    cm.focus();

    $('#edit').on("submit", function () {
      cm.markClean();
    });

    $(window).on('beforeunload', function () {
      if (!cm.isClean()) {
        return "There are unsaved changes.";
      }
    });
  }
});