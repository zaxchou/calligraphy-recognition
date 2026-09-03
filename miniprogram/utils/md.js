function cleanText(text) {
  var s = String(text == null ? '' : text)
  s = s.replace(/NaN|nan|Nan/gi, '—').replace(/Infinity/gi, '—')

  // LaTeX math: $...$ and $$...$$ (same as backend _STRIP_LATEX_RE)
  s = s.replace(/\$\$[^$]*\$\$/g, '')
  s = s.replace(/\$[^$]*\$/g, '')

  // LaTeX environments
  s = s.replace(/\\begin\{[^}]*\}/g, '')
  s = s.replace(/\\end\{[^}]*\}/g, '')

  // LaTeX text commands → Unicode equivalents
  var latexMap = {
    '\\textcircled': '○', '\\circledR': '®', '\\textregistered': '®',
    '\\texttrademark': '™', '\\textcopyright': '©', '\\textbullet': '•',
    '\\textdagger': '†', '\\textdaggerdbl': '‡', '\\textellipsis': '…',
    '\\textendash': '–', '\\textemdash': '—',
    '\\textasciitilde': '~', '\\textasciicircum': '^', '\\textbackslash': '\\',
    '\\textbar': '|', '\\textless': '<', '\\textgreater': '>',
    '\\textquoteleft': "'", '\\textquoteright': "'",
    '\\textquotedblleft': '"', '\\textquotedblright': '"',
    '\\textopenbullet': '◦', '\\textperiodcentered': '·',
    '\\textmu': 'µ', '\\texttimes': '×',
    '\\textdegree': '°', '\\textpm': '±'
  }
  for (var key in latexMap) {
    // Match \textcircled{2} → ○2, \textcircled → ○
    var re = new RegExp(key.replace(/\\/g, '\\\\') + '(\\{[^}]*\\})?', 'gi')
    s = s.replace(re, function (match, arg) {
      if (arg) {
        // Extract content inside braces
        var inner = arg.replace(/[{}]/g, '')
        return latexMap[key] + inner
      }
      return latexMap[key]
    })
  }

  // Strip remaining unrecognized LaTeX commands: \foo or \foo{bar} → just bar
  s = s.replace(/\\[a-zA-Z]+\{([^}]*)\}/g, '$1')
  s = s.replace(/\\[a-zA-Z]+/g, '')

  return s
}

function spanHtml(s) {
  var t = cleanText(s.text).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  return s.bold ? '<strong>' + t + '</strong>' : t
}

function blocksToHtml(mdText) {
  var lines = cleanText(mdText).split('\n')
  var html = ''
  var i = 0

  while (i < lines.length) {
    var line = lines[i]
    var t = line.trim()

    if (!t) { html += '<p style="min-height:0.8em"></p>'; i++; continue }

    // Table
    if (/^\|.+\|$/.test(t) && i + 1 < lines.length && /^\|(\s*[-:]+\s*\|)+\s*$/.test(lines[i + 1].trim())) {
      var headers = t.replace(/^\||\|$/g, '').split('|').map(function(c){return c.trim()})
      html += '<table style="width:100%;border-collapse:collapse;border:1px solid #e7e5e4;border-radius:12px;overflow:hidden;margin:12px 0">'
      html += '<thead><tr>'
      for (var hi = 0; hi < headers.length; hi++) {
        html += '<th style="padding:10px 8px;background:#faf8f3;font-size:13px;font-weight:600;color:#444;text-align:center;border-right:1px solid #f0ede8">' + cleanText(headers[hi]) + '</th>'
      }
      html += '</tr></thead><tbody>'
      var j = i + 2
      while (j < lines.length && /^\|.+\|$/.test(lines[j].trim())) {
        var cells = lines[j].trim().replace(/^\||\|$/g, '').split('|').map(function(c){return c.trim()})
        html += '<tr>'
        for (var ci = 0; ci < cells.length; ci++) {
          var cell = cleanText(cells[ci]).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
          html += '<td style="padding:9px 8px;font-size:13px;color:#444;text-align:center;border-right:1px solid #f0ede8;border-top:1px solid #f0ede8">' + cell + '</td>'
        }
        html += '</tr>'
        j++
      }
      html += '</tbody></table>'
      i = j
      continue
    }

    // HR
    if (/^-{3,}$/.test(t) || /^\*{3,}$/.test(t) || /^_{3,}$/.test(t)) {
      html += '<hr style="border:none;height:1px;background:#e7e5e4;margin:16px 0">'
      i++; continue
    }

    // Headings
    if (t.lastIndexOf('### ', 0) === 0) {
      html += '<h3 style="font-size:15px;font-weight:600;color:#444;margin:16px 0 6px">' + inlineHtml(t.slice(4)) + '</h3>'
    } else if (t.lastIndexOf('## ', 0) === 0) {
      html += '<h2 style="font-size:17px;font-weight:700;color:#1c1917;margin:20px 0 10px;border-bottom:2px solid #f0ede8;padding-bottom:6px">' + inlineHtml(t.slice(3)) + '</h2>'
    } else if (t.lastIndexOf('# ', 0) === 0) {
      html += '<h2 style="font-size:17px;font-weight:700;color:#1c1917;margin:20px 0 10px;border-bottom:2px solid #f0ede8;padding-bottom:6px">' + inlineHtml(t.slice(2)) + '</h2>'
    } else if (t.lastIndexOf('- ', 0) === 0 || t.lastIndexOf('* ', 0) === 0) {
      html += '<p style="font-size:15px;color:#444;margin:5px 0;line-height:1.8;padding-left:4px"><span style="color:#a8a29e;margin-right:8px">—</span>' + inlineHtml(t.slice(2)) + '</p>'
    } else if (/^\d+\.\s/.test(t)) {
      html += '<p style="font-size:15px;color:#444;margin:5px 0;line-height:1.8;padding-left:4px"><span style="color:#a8a29e;margin-right:8px">' + t.replace(/^(\d+)\.\s.*/, '$1') + '.</span>' + inlineHtml(t.replace(/^\d+\.\s/, '')) + '</p>'
    } else {
      html += '<p style="font-size:15px;color:#444;margin:6px 0;line-height:1.9">' + inlineHtml(t) + '</p>'
    }
    i++
  }

  return html
}

function inlineHtml(text) {
  var s = cleanText(text)
  // Bold
  s = s.replace(/\*\*(.+?)\*\*/g, '<strong style="font-weight:700;color:#1c1917">$1</strong>')
  // Images: ![alt](url)
  s = s.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, function(match, alt, url) {
    return '<img src="' + url + '" alt="' + alt + '" style="max-width:100%;height:auto;border-radius:8px;margin:8px 0" />'
  })
  // Links: [text](url) — render as styled text (mini program rich-text doesn't support <a> navigation well)
  s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<span style="color:#5b7a8c;text-decoration:underline">$1</span>')
  return s
}

module.exports = {
  parseBlocks: null,
  parseInline: null,
  cleanText: cleanText,
  blocksToHtml: blocksToHtml
}
