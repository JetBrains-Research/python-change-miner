$(document).ready(function() {
    function wrapLine(baseLineURL, number, content) {
        var className = 'line', url = '', target = '';
        if (content.includes('<span class="highlighted">')) {
            target = '_blank';
            className += ' clickable';
            url = (baseLineURL + number);
        } else {
            url = '#';
        }

        return '<a class="' + className + '" href="' + url + '" target="' + target + '">' +
            '<div class="line-number">' + number + '</div>' +
            '<div class="line-content">' + content + '</div></a>';
    }

    $('pre.code').each(function() {
        hljs.highlightBlock(this);

        var codeElement = $(this);
        var baseLineURL = codeElement.attr('data-base-line-url') || '#';
        var startLineNumber = parseInt(codeElement.attr('data-line-number') || 1);

        var lines = [];
        _.each(codeElement.html().split('\n'), function(line, index) {
            var formattedLine = wrapLine(baseLineURL, startLineNumber + index, line || ' ');
            lines.push(formattedLine);
        });

        var startHighlighted = null;
        var endHighlighted = null;
        _.each(lines.slice(), function (line, index) {
            if (line.includes('<span class="highlighted">')) {
                if (startHighlighted === null) {
                    startHighlighted = index;
                }
                endHighlighted = index;
            }
        });

        startHighlighted = Math.max(startHighlighted-5, 0);
        endHighlighted = Math.min(endHighlighted+5, lines.length-1);

        var storage = window.jbr_code_changes || {};
        var version = codeElement.attr('data-code-version');
        storage[version] = {
            'lines': lines,
            'is_top_expanded': false,
            'is_bottom_expanded': false,
            'highlighted_start_line': startHighlighted,
            'highlighted_end_line': endHighlighted
        };
        window.jbr_code_changes = storage;

        if (startHighlighted > 0) {
            $('[data-action="toggle-expand"][data-kind="top"][data-code-version="' + version + '"]').show();
        }
        if (endHighlighted < lines.length - 1) {
            $('[data-action="toggle-expand"][data-kind="bottom"][data-code-version="' + version + '"]').show();
        }

        var newContent = lines.slice(startHighlighted, endHighlighted+1).join('');
        codeElement.html(newContent);
    });
    
    $('#before_code_block .title, #after_code_block .title').click(function () {
        var code = $('pre.code', $(this).parent());
        selectText(code[0]);
        document.execCommand('copy');
        window.getSelection().removeAllRanges();
        alert('Copied');
    });

    function selectText(element) {
        var selection = window.getSelection();
        var range = document.createRange();
        range.selectNodeContents(element);
        selection.removeAllRanges();
        selection.addRange(range);
    }

    $('[data-action="toggle-expand"]').click(function() {
        $(this).toggleClass('expanded');
        var kind = $(this).attr('data-kind');

        var version = $(this).attr('data-code-version');
        var lines =  window.jbr_code_changes[version]['lines'];

        var startLine, endLine;
        if (kind === 'top') {
            startLine = window.jbr_code_changes[version]['is_top_expanded']
                ? window.jbr_code_changes[version]['highlighted_start_line'] : 0;
            endLine = window.jbr_code_changes[version]['is_bottom_expanded']
                ? lines.length-1 : window.jbr_code_changes[version]['highlighted_end_line'];
            window.jbr_code_changes[version]['is_top_expanded'] = !window.jbr_code_changes[version]['is_top_expanded'];
        } else {
            startLine = window.jbr_code_changes[version]['is_top_expanded']
                ? 0 : window.jbr_code_changes[version]['highlighted_start_line'];
            endLine = window.jbr_code_changes[version]['is_bottom_expanded']
                ? window.jbr_code_changes[version]['highlighted_end_line'] : lines.length-1;
            window.jbr_code_changes[version]['is_bottom_expanded'] = !window.jbr_code_changes[version]['is_bottom_expanded'];
        }

        var codeElement = $('pre.code[data-code-version=' + version + ']');
        var newContent = lines.slice(startLine, endLine+1).join('');
        codeElement.html(newContent);
    });
});
