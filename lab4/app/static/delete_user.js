function fillDeleteModalInfo(event) {
    let deleteUrl = event.relatedTarget.dataset.deleteUrl;
    let fio = event.relatedTarget.dataset.name;
    
    let title = event.target.querySelector(".modal-user-fio");
    title.innerHTML = "Вы действительно хотите удалить " + fio;
    
    let modalForm = event.target.querySelector("form");
    modalForm.action = deleteUrl;
}

window.onload = function () {
    let deleteModalWindow = document.getElementById("delete_user_modal");
    deleteModalWindow.addEventListener("show.bs.modal", fillDeleteModalInfo);
}