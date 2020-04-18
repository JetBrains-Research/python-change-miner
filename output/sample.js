$(document).ready(function() {
    function wrapLine(baseLineURL, number, content) {
        let className = 'line', url = '', target = '';
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

        const code = $(this);
        const baseLineURL = code.attr('data-base-line-url') || '#';
        const startLineNumber = parseInt(code.attr('data-line-number') || 1);

        const lines = code.html().split('\n');
        let newContent = '';
        _.each(lines, function(line, index) {
            newContent += wrapLine(baseLineURL, startLineNumber + index, line || ' ');
        });
        code.html(newContent);
    });
    
    $('.title').click(function () {
        var code = $('pre.code', $(this).parent());
        selectText(code[0]);
        document.execCommand('copy');
        window.getSelection().removeAllRanges();
        alert('Copied');
    });

    function selectText(element) {
        let selection = window.getSelection();
        let range = document.createRange();
        range.selectNodeContents(element);
        selection.removeAllRanges();
        selection.addRange(range);
    }
});
