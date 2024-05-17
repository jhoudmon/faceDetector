const input = document.getElementById('input');

const previewPhoto = () => {
    const file = input.files;
    if (file) {
        const fileReader = new FileReader();
        const preview = document.getElementById('preview');
        fileReader.onload = event => {
            preview.setAttribute('src', event.target.result);
        }
        fileReader.readAsDataURL(file[0]);
    }
}

input.addEventListener('change', previewPhoto);