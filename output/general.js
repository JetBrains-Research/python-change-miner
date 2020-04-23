$(document).ready(function() {
    $('[data-target="visibility"]').hide();

    $('[data-action="copy"]').click(function () {
        var target = $('[data-target="copy"]', $(this).parent());
        selectText(target[0]);
        document.execCommand('copy');
        window.getSelection().removeAllRanges();
        alert('Copied');
    });

    $('[data-action="visibility"]').click(function () {
        var target = $('[data-target="visibility"]', $(this).parent());
        target.toggle();
    });

    function selectText(element) {
        let selection = window.getSelection();
        let range = document.createRange();
        range.selectNodeContents(element);
        selection.removeAllRanges();
        selection.addRange(range);
    }
});
