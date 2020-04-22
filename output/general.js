$(document).ready(function() {
    $('[data-action="copy"]').click(function () {
        var target = $('[data-target="copy"]', $(this).parent());
        selectText(target[0]);
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
