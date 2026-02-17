function changeImage(imageUrl, element) {
    document.getElementById('mainDisplayImage').src = imageUrl;
    document.querySelectorAll('.thumbnail-wrapper').forEach(wrapper => {
        wrapper.classList.remove('border-success', 'border-2');
    });
    element.classList.add('border-success', 'border-2');
}