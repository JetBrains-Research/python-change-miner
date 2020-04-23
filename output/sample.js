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

        var storage = window.jbr_code_changes || {};
        var key = codeElement.attr('data-code-version');
        storage[key] = {'original': lines.slice(), 'is_expanded': false};

        var sameLines = true;
        _.every(lines.slice().reverse(), function (line) {
            if (!line.includes('<span class="highlighted">')) {
                lines.pop();
                sameLines = false;
                return true;
            }

            return false;
        });

        storage[key]['expanded'] = lines;
        window.jbr_code_changes = storage;

        var newContent = lines.join('');
        newContent += (sameLines ? '' : '<div class="expand-btn" data-action="toggle-expand">' +
            '&#8595;&#8595;&#8595;&#8595;&#8595;</div>');
        codeElement.html(newContent);
    });
    
    $('.title').click(function () {
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

    $('pre.code').on('click', '[data-action="toggle-expand"]', function () {
        var codeElement = $(this).closest('pre.code');
        var version = codeElement.attr('data-code-version');
        var isExpanded = window.jbr_code_changes[version]['is_expanded'];

        var lines = isExpanded ? window.jbr_code_changes[version]['expanded'] : window.jbr_code_changes[version]['original'];
        var newContent =
            lines.join('') + '<div class="expand-btn" data-action="toggle-expand">'
            + (isExpanded ? '&#8595;&#8595;&#8595;&#8595;&#8595' : '&#8593;&#8593;&#8593;&#8593;&#8593;')
            + '</div>';

        codeElement.html(newContent);
        window.jbr_code_changes[version]['is_expanded'] = !isExpanded;
    });
});
