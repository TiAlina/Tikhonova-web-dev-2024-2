function openDeleteModal(title, bookId) {
    const modal = new bootstrap.Modal(document.getElementById('deleteBookModal'));
    document.getElementById('deleteBookMessage').innerText = `Вы уверены, что хотите удалить книгу "${title}"?`;
    document.getElementById('confirmDeleteButton').addEventListener('click', function() {
        deleteBook(bookId);
        modal.hide();
    });
    modal.show();
}

function deleteBook(bookId) {
    fetch(`/delete/${bookId}`, {
        method: 'DELETE',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(data => {
        alert(data.message);
        window.location.reload();
    })
    .catch(error => {
        console.error('There was an error!', error);
    });
}


function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
