function previewAvatar(event) {
    const reader = new FileReader();
    reader.onload = function() {
        const output = document.getElementById('profile_preview');
        output.src = reader.result;
    };
    if (event.target.files[0]) {
        reader.readAsDataURL(event.target.files[0]);
    }
}