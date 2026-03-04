*** Settings ***
Documentation    Test case

Library        RPA.Browser.Selenium
Library        RPA.Desktop
Library        RPA.JSON
Library        OperatingSystem

*** Tasks ***
DirectumRX login
    Open Available Browser   https://directumrx-test.uktaif.ru/client/#/folder/2593
    Maximize Browser Window
    Set Selenium Speed       1 seconds

    &{data}=    Load JSON from file    processed_data.json
    &{login}=   Load JSON from file    login.json

    ${username}=  Get value from JSON  ${login}  $.username
    ${password}=  Get value from JSON  ${login}  $.password

    RPA.Desktop.Type Text    ${username}
    RPA.Desktop.Press Keys   tab

    RPA.Desktop.Type Text    ${password}
    RPA.Desktop.Press Keys   tab
    RPA.Desktop.Press keys   tab
    RPA.Desktop.Press keys   enter
    RPA.Desktop.Press keys   enter
    
    Wait Until Element Is Visible    class:entity-creation-menu    20

    RPA.Desktop.Press keys   enter
    Click Element            class:entity-creation-menu
    Click Element            xpath://*[contains(text(),"Прочее…")]
    Double Click Element     xpath://*[contains(text(),"Входящее письмо")]    

    Double Click Element            xpath://*[contains(text(),"Содержание")]    
    ${content}=              Get value from JSON    ${data}    $.content
    RPA.Browser.Selenium.Press Keys  class:text-editor_focused    ${content}
    
    Set Selenium Speed       3 seconds

    Double Click Element            xpath://*[contains(text(),"Корреспондент")]    
    ${content}=              Get value from JSON    ${data}    $.correspondent
    RPA.Browser.Selenium.Press Keys  class:lookup_focused    ${content}
    Sleep                    5s
    RPA.Desktop.Press keys   enter
    
    Double Click Element     xpath://*[@placeholder='<Сотрудник, на имя которого поступил документ>']    
    ${content}=              Get value from JSON    ${data}    $.recipient
    RPA.Browser.Selenium.Press Keys  class:lookup_focused    ${content}
    Sleep                    5s
    RPA.Desktop.Press keys   enter
    RPA.Desktop.Press keys   enter
    
    Double Click Element            xpath://*[contains(text(),"Дата от")]  
    ${content}=              Get value from JSON    ${data}    $.dateFrom
    RPA.Browser.Selenium.Press Keys  class:datetime-editor_focused    ${content}
    RPA.Desktop.Press keys   enter
    
    Double Click Element            xpath://*[contains(text(),"№")]  
    ${content}=              Get value from JSON    ${data}    $.number
    RPA.Browser.Selenium.Press Keys  class:string-editor_focused    ${content}
    RPA.Desktop.Press keys   enter
    
    Double Click Element            xpath://*[contains(text(),"Подписал")]  
    ${content}=              Get value from JSON    ${data}    $.signedBy
    RPA.Browser.Selenium.Press Keys  class:lookup_focused    ${content}
    Sleep                    5s
    RPA.Desktop.Press keys   enter
    RPA.Desktop.Press keys   enter

     Click Element            xpath://div[@title='Создание версии из файла']
    ${file_name}=  Get File  filename.txt
    ${file_path}=            Set Variable    /home/stryginavm@uktaif.ru/Документы/ai-agent/scripts/input_data/${file_name}

    Choose File    xpath://input[@type='file']    ${file_path}

   
    Double Click Element     xpath://*[@title='Сохранение изменений и закрытие карточки']    

